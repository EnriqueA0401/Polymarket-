"""H038 — descarga (reanudable) de Kalshi: series, eventos liquidados, muestra por hash de evento,
mercados de entrenamiento y trades de la ventana (t−1 h, t].

Uso:  PYTHONPATH=src python3 experiments/h038_fetch.py {series|events|markets|trades} [N_BUDGET]

Regla de muestreo (fijada por presupuesto ANTES de ver resultados): los eventos liquidados se
recorren en orden creciente de sha256(event_ticker); se descargan sus mercados y se para cuando el
número acumulado de mercados de ENTRENAMIENTO "elegibles" (binarios, volumen > 0, abiertos en algún
momento de (t−1 h, t]) alcanza N_BUDGET. Equivale a muestrear eventos con hash < umbral, con el
umbral determinado solo por recuentos (nunca por resultados ni precios).
Se omiten eventos con strike_date ≥ 2026-04-20 (holdout seguro; sus mercados no pueden liquidarse
antes del 2026-04-12 con t dentro de su vida… salvo cierres anticipados, que quedan fuera de la
ventana de t de todos modos) y series multivariantes (KXMVE*, combos RFQ).
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

from pmq import h038
from pmq.h038 import CACHE, k_get

os.makedirs(CACHE, exist_ok=True)
EV_PATH = os.path.join(CACHE, "events.parquet")
SAMPLE_PATH = os.path.join(CACHE, "sample_markets.parquet")


def log(*a):
    print(pd.Timestamp.now(tz="UTC").strftime("%H:%M:%S"), *a, flush=True)


def stage_series():
    r = k_get("/series", {})
    json.dump(r["series"], open(os.path.join(CACHE, "series.json"), "w"))
    log("series", len(r["series"]))


def stage_events():
    ck = os.path.join(CACHE, "events_ck.json")
    st = json.load(open(ck)) if os.path.exists(ck) else {"cursor": None, "pages": 0, "done": False}
    part = os.path.join(CACHE, "events_parts")
    os.makedirs(part, exist_ok=True)
    while not st["done"]:
        q = {"status": "settled", "limit": 200}
        if st["cursor"]:
            q["cursor"] = st["cursor"]
        r = k_get("/events", q)
        ev = [{"event_ticker": e["event_ticker"], "series_ticker": e.get("series_ticker"),
               "category": e.get("category"), "strike_date": e.get("strike_date"),
               "mutually_exclusive": e.get("mutually_exclusive"), "title": (e.get("title") or "")[:120]}
              for e in r.get("events", [])]
        if ev:
            pd.DataFrame(ev).to_parquet(os.path.join(part, f"{st['pages']:06d}.parquet"))
        st["pages"] += 1
        st["cursor"] = r.get("cursor")
        st["done"] = not st["cursor"] or not ev
        json.dump(st, open(ck, "w"))
        if st["pages"] % 100 == 0:
            log("events pages", st["pages"])
    df = pd.concat([pd.read_parquet(os.path.join(part, f)) for f in sorted(os.listdir(part))])
    df = df.drop_duplicates("event_ticker")
    df.to_parquet(EV_PATH)
    log("events total", len(df))


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


def stage_markets(budget):
    ev = pd.read_parquet(EV_PATH)
    ev = ev[~ev.series_ticker.fillna("").str.startswith("KXMVE")]
    sd = pd.to_datetime(ev.strike_date, utc=True, errors="coerce")
    ev = ev[~(sd >= pd.Timestamp("2026-04-20", tz="UTC"))].copy()
    ev["h"] = ev.event_ticker.map(h038.ev_hash)
    ev = ev.sort_values("h").reset_index(drop=True)
    log("events candidatos", len(ev))
    n_el, rows, i, B = 0, [], 0, 64
    with ThreadPoolExecutor(8) as ex:
        while n_el < budget and i < len(ev):
            chunk = ev.iloc[i:i + B]
            res = list(ex.map(h038.event_markets, chunk.event_ticker))
            for (_, e), r in zip(chunk.iterrows(), res):
                for x in eligible_rows(r["markets"]):
                    x.update(series_ticker=e.series_ticker, category=e.category, ev_h=e.h,
                             n_holdout_dropped_ev=r["n_holdout_dropped"])
                    rows.append(x)
                    n_el += x["eligible"]
                if n_el >= budget:
                    i = int(_) + 1
                    break
            else:
                i += B
            if (i // B) % 20 == 0:
                log("events", i, "markets", len(rows), "elegibles", n_el)
    df = pd.DataFrame(rows)
    df["n_events_scanned"] = i
    df["h_threshold"] = float(ev.h.iloc[i - 1])
    df.to_parquet(SAMPLE_PATH)
    log("FIN markets", len(df), "elegibles", int(df.eligible.sum()), "eventos", i,
        "umbral hash", df.h_threshold.iloc[0])


def stage_trades():
    df = pd.read_parquet(SAMPLE_PATH)
    el = df[df.eligible]
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
    elif s == "events":
        stage_events()
    elif s == "markets":
        stage_markets(int(sys.argv[2]))
    elif s == "trades":
        stage_trades()
