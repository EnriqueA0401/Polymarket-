"""H038 — descarga (reanudable, caché en data/h038) de Kalshi: series, universo de mercados
históricos de entrenamiento, muestra por hash de evento y trades de la ventana (t−1 h, t].

Uso:  PYTHONPATH=src python3 experiments/h038_fetch.py {series|universe|sample N_BUDGET|trades}

- universe: /historical/markets por serie (todas las series de /series salvo KXMVE*, combos RFQ). Se
  guardan SOLO los mercados liquidados < 2026-04-12; los de holdout se cuentan y se descartan.
  Series de 15 min / horarias: si ningún mercado de su página más reciente abre ≥ 25 h antes del
  cierre previsto, se marcan estructuralmente inelegibles y no se paginan (ahorro de presupuesto).
- sample: regla fijada por presupuesto ANTES de ver precios o resultados: los mercados elegibles se
  ordenan por sha256(event_ticker) y se toman eventos completos en orden creciente de hash hasta
  alcanzar N_BUDGET mercados elegibles (= muestrear eventos con hash ≤ umbral; el umbral depende solo
  de recuentos).
- trades: para cada mercado muestreado y elegible, trades de (t−1 h, t] y, si la ventana está vacía,
  el último trade ≤ t−1 h. Nunca se pide nada posterior a t.
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

from pmq import h038
from pmq.h038 import CACHE, k_get

os.makedirs(CACHE, exist_ok=True)


def log(*a):
    print(pd.Timestamp.now(tz="UTC").strftime("%H:%M:%S"), *a, flush=True)


def stage_series():
    r = k_get("/series", {})
    json.dump(r["series"], open(os.path.join(CACHE, "series.json"), "w"))
    log("series", len(r["series"]))


HF = ("fifteen_min", "hourly")


def series_markets(s):
    """Todos los mercados históricos de la serie (paginados); guarda SOLO entrenamiento (liquidados
    < HOLDOUT_START) con campos compactos. Series de alta frecuencia: si en la primera página (la más
    reciente) ningún mercado abre ≥ 24 h antes de su cierre previsto, se marca estructuralmente
    inelegible y no se pagina más."""
    d = os.path.join(CACHE, "sm")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{s['ticker']}.parquet")
    if os.path.exists(path):
        return
    rows, n_hold, n_mve, cur, pages, skipped = [], 0, 0, None, 0, False
    while True:
        q = {"series_ticker": s["ticker"], "limit": 1000}
        if cur:
            q["cursor"] = cur
        r = k_get("/historical/markets", q) or {}
        ms = r.get("markets", [])
        pages += 1
        if pages == 1 and s.get("frequency") in HF and ms:
            span = [(h038.schedule_ref(m).timestamp() - pd.Timestamp(m["open_time"]).timestamp())
                    for m in ms if m.get("open_time")]
            if span and max(span) < h038.HORIZON + h038.WINDOW:
                skipped = True
        for m in ms:
            st = m.get("settlement_ts") or m.get("close_time")
            if not st or pd.Timestamp(st) >= h038.HOLDOUT_START:
                n_hold += 1
                continue
            if m.get("mve_collection_ticker"):
                n_mve += 1
                continue
            rows.append({k: m.get(k) for k in h038.M_KEEP})
        cur = r.get("cursor")
        if skipped or not cur or not ms:
            break
    df = pd.DataFrame(rows, columns=list(h038.M_KEEP))
    df["series_ticker"] = s["ticker"]
    df.attrs = {}
    meta = {"series": s["ticker"], "n_train": len(df), "n_holdout_dropped": n_hold, "n_mve": n_mve,
            "pages": pages, "skipped_structural": skipped}
    df.to_parquet(path + ".tmp.parquet")
    with open(path + ".meta.json", "w") as f:
        json.dump(meta, f)
    os.replace(path + ".tmp.parquet", path)


def stage_universe():
    ser = json.load(open(os.path.join(CACHE, "series.json")))
    ser = [s for s in ser if not s["ticker"].startswith("KXMVE")]
    # alta frecuencia al final (más páginas)
    ser.sort(key=lambda s: s.get("frequency") in HF)
    log("series a recorrer", len(ser))
    done = [0]

    def one(s):
        try:
            series_markets(s)
        except Exception as e:  # noqa: BLE001
            log("ERROR", s["ticker"], e)
        done[0] += 1
        if done[0] % 500 == 0:
            log("series hechas", done[0])

    with ThreadPoolExecutor(8) as ex:
        list(ex.map(one, ser))
    log("FIN universe")


def eligible_rows(markets):
    rows = []
    for m in markets:
        ref = h038.schedule_ref(m)
        if pd.isna(ref):
            continue
        t = ref.timestamp() - h038.HORIZON
        op = pd.Timestamp(m["open_time"]).timestamp() if m.get("open_time") else float("inf")
        cl = pd.Timestamp(m["close_time"]).timestamp() if m.get("close_time") else -float("inf")
        vol = float(m.get("volume_fp") or 0)
        el = (m.get("market_type") == "binary") and vol > 0 and op < t and cl > t - h038.WINDOW
        rows.append({**m, "t": t, "eligible": bool(el)})
    return rows


def load_universe():
    d = os.path.join(CACHE, "sm")
    fs = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".parquet") and ".tmp" not in f]
    df = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    meta = pd.DataFrame([json.load(open(f + ".meta.json")) for f in fs])
    return df, meta


def stage_sample(budget):
    df, meta = load_universe()
    ser = {s["ticker"]: s for s in json.load(open(os.path.join(CACHE, "series.json")))}
    df = pd.DataFrame(eligible_rows(df.to_dict("records")))
    df["category"] = df.series_ticker.map(lambda x: ser.get(x, {}).get("category"))
    df["fee_mult"] = df.series_ticker.map(lambda x: ser.get(x, {}).get("fee_multiplier", 1.0))
    df["fee_type"] = df.series_ticker.map(lambda x: ser.get(x, {}).get("fee_type"))
    df["ev_h"] = df.event_ticker.map(h038.ev_hash)
    df = df.sort_values(["ev_h", "ticker"]).reset_index(drop=True)
    cum = df.eligible.cumsum()
    if cum.iloc[-1] <= budget:
        thr = 1.0
    else:
        last_ev = df.event_ticker[cum.searchsorted(budget)]
        thr = float(df.loc[df.event_ticker == last_ev, "ev_h"].iloc[0])
    df["sampled"] = df.ev_h <= thr
    df.attrs = {}
    df.to_parquet(os.path.join(CACHE, "universe_train.parquet"))
    meta.to_csv(os.path.join(CACHE, "series_meta.csv"), index=False)
    log("universo entrenamiento", len(df), "elegibles", int(df.eligible.sum()), "umbral hash", thr,
        "muestreados elegibles", int((df.sampled & df.eligible).sum()))


def stage_trades():
    df = pd.read_parquet(os.path.join(CACHE, "universe_train.parquet"))
    el = df[df.eligible & df.sampled]
    log("trades para", len(el))
    done = [0]

    def one(a):
        h038.market_trades(a[0], a[1])
        done[0] += 1
        if done[0] % 2000 == 0:
            log("trades", done[0])

    with ThreadPoolExecutor(8) as ex:
        list(ex.map(one, zip(el.ticker, el.t)))
    log("FIN trades", done[0])


if __name__ == "__main__":
    s = sys.argv[1]
    if s == "series":
        stage_series()
    elif s == "universe":
        stage_universe()
    elif s == "sample":
        stage_sample(int(sys.argv[2]))
    elif s == "trades":
        stage_trades()
