"""H042 [BIN] — Coherencia interna de Kalshi: cubos mutuamente excluyentes y escaleras de strikes.

Protocolo G0 (HYPOTHESES.md, fijado 2026-10-15 antes de ver datos). Cada snapshot:
  - Eventos abiertos de Kalshi con mercados anidados (/events?status=open&with_nested_markets=true), ≥ 2 mercados.
  - Libros de todos sus mercados activos (/markets/orderbooks, lotes de ≤ 100 tickers, agrupados por evento
    para que las patas de un evento salgan de la misma respuesta; respaldo /markets/{t}/orderbook).
  - Kalshi solo publica bids de YES y de NO: un ask de YES a p es un bid de NO a 1 − p (h039.k_asks).
  - Coste de C = 10 contratos por pata barriendo profundidad, comisión taker ceil_al_céntimo(0.07·c·P·(1−P))
    por nivel (cada nivel como orden separada: pesimista; idéntico a "por pata" si llena en un nivel;
    multiplicador de serie 1, pesimista). Sin profundidad suficiente → NaN (sin oportunidad).
  Estrategias:
  - me_yes: evento mutually_exclusive con cobertura completa verificada (cubos numéricos contiguos con
    colas −∞ y +∞, ver coverage()); comprar C YES de cada mercado activo → pago C.
  - me_no: evento mutually_exclusive (cobertura irrelevante): comprar C NO de cada activo → pago ≥ C·(n−1).
  - ladder: evento no excluyente con mercados del mismo strike_type ('greater'/'greater_or_equal' con
    floor_strike, 'less'/'less_or_equal' con cap_strike), misma plantilla de reglas y mismo close_time.
    K1 < K2: above → YES(>K1) + NO(>K2); below → YES(<K2) + NO(<K1). Pago ≥ C.
  Beneficio neto = pago − coste; % del capital = beneficio/coste; días hasta el close_time más tardío de las
  patas (mín. 1 h); anualizado simple = %·365/días. Oportunidad G0: % ≥ 0.5 % y anualizado ≥ 20 %.
Uso: PYTHONPATH=src python -m pmq.h042 [--loop MINUTOS] → data/h042/opps.csv (+ libros crudos con beneficio > 0).
"""
import argparse, gzip, json, math, os, re, time
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
import numpy as np
import pandas as pd

from pmq.h023 import k_get
from pmq.h039 import k_asks, k_buy_cost, k_fee  # noqa: F401  (k_fee reexportada para tests)
from pmq.universe import DATA

OUT = os.path.join(DATA, "h042")
C = 10                       # contratos por pata
MIN_RET, MIN_ANN = 0.005, 0.20
BATCH = 100                  # máximo de tickers por /markets/orderbooks
NUM = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?%?")
UP_T, DOWN_T = ("greater", "greater_or_equal"), ("less", "less_or_equal")


# ---------------------------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------------------------
def open_events():
    evs, cur = [], None
    while True:
        p = {"status": "open", "with_nested_markets": "true", "limit": 200}
        if cur:
            p["cursor"] = cur
        d = k_get("/events", p) or {}
        evs += d.get("events") or []
        cur = d.get("cursor")
        if not cur or not d.get("events"):
            return [e for e in evs if len(e.get("markets") or []) >= 2]


def active(e):
    return [m for m in e.get("markets") or [] if m.get("status") == "active"]


def _chunks(evs):
    """Lotes de ≤ BATCH tickers sin partir eventos (salvo eventos de más de BATCH mercados)."""
    out, cur = [], []
    for e in evs:
        t = [m["ticker"] for m in active(e)]
        if len(cur) + len(t) > BATCH and cur:
            out.append(cur); cur = []
        while len(t) > BATCH:
            out.append(t[:BATCH]); t = t[BATCH:]
        cur += t
    if cur:
        out.append(cur)
    return out


def books(evs, workers=6):
    """ticker → orderbook_fp ({'yes_dollars': [[p, s], ...], 'no_dollars': [...]})."""
    def one(ch):
        d = k_get("/markets/orderbooks", {"tickers": ch}) or {}
        got = {b["ticker"]: b.get("orderbook_fp") or {} for b in d.get("orderbooks") or []}
        for t in ch:                       # respaldo individual si el lote omitió alguno
            if t not in got:
                got[t] = ((k_get(f"/markets/{t}/orderbook", {}) or {}).get("orderbook_fp") or {})
        return got
    out = {}
    with ThreadPoolExecutor(workers) as ex:
        for g in ex.map(one, _chunks(evs)):
            out.update(g)
    return out


# ---------------------------------------------------------------------------------------------
# Costes
# ---------------------------------------------------------------------------------------------
def leg_cost(book, side, c=C):
    """Coste (USD, con comisión) de comprar c contratos de `side` barriendo el libro. NaN sin profundidad."""
    return k_buy_cost(k_asks(book, side), c)


def best_ask(book, side):
    a = k_asks(book, side)
    return a[0][0] if a else np.nan


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _days(ms, ts):
    t = pd.to_datetime([m.get("close_time") for m in ms], utc=True, errors="coerce").max()
    return max((t - ts).total_seconds() / 86400, 1 / 24) if pd.notna(t) else np.nan


# ---------------------------------------------------------------------------------------------
# Cobertura de cubos excluyentes
# ---------------------------------------------------------------------------------------------
def _is_mult(x, g):
    return g > 0 and abs(x / g - round(x / g)) < 1e-6


def coverage(ms):
    """(ok, motivo). ok solo si los cubos numéricos cubren (−∞, +∞) sin huecos: una cola inferior
    ('less' x<cap / 'less_or_equal' x≤cap), una superior ('greater' x>floor / 'greater_or_equal' x≥floor) y
    cubos 'between' [floor, cap] inclusivos. Huecos entre 'between' consecutivos: todos iguales a un paso g
    del que son múltiplos todos los límites (granularidad de publicación del dato, p. ej. 1 °F, 0.1 pp,
    0.01 $); hueco 0 también vale. Cola 'greater' exige floor ≤ cap del último cubo y 'less' cap ≥ floor del
    primero; las versiones _or_equal admiten hueco ≤ g. Cualquier otra estructura → no verificable."""
    st = [m.get("strike_type") for m in ms]
    if any(s not in UP_T + DOWN_T + ("between",) for s in st):
        return False, "no_numerico"
    lo = [m for m in ms if m.get("strike_type") in DOWN_T]
    hi = [m for m in ms if m.get("strike_type") in UP_T]
    bw = [m for m in ms if m.get("strike_type") == "between"]
    if len(lo) != 1 or len(hi) != 1:
        return False, "sin_colas"
    lo, hi = lo[0], hi[0]
    lc, hf = _f(lo.get("cap_strike")), _f(hi.get("floor_strike"))
    iv = sorted((_f(m.get("floor_strike")), _f(m.get("cap_strike"))) for m in bw)
    if lc is None or hf is None or any(a is None or b is None or b < a for a, b in iv):
        return False, "strike_nulo"
    if not iv:                                            # solo dos colas
        if lo["strike_type"] == "less" and hi["strike_type"] == "greater":
            return (hf <= lc, "ok" if hf <= lc else "hueco")
        return False, "colas_sin_cubos"
    gaps = [b0 - a1 for (_, a1), (b0, _) in zip(iv, iv[1:])]
    if any(g < -1e-9 for g in gaps):
        return False, "solapamiento"
    pos = [g for g in gaps if g > 1e-9]
    g = pos[0] if pos else 0.0
    if any(abs(x - g) > 1e-6 * max(1, g) for x in pos):
        return False, "huecos_desiguales"
    bounds = [x for ab in iv for x in ab] + [lc, hf]
    if g > 0 and not all(_is_mult(x, g) for x in bounds):
        return False, "limites_no_multiplos"
    first, last = iv[0][0], iv[-1][1]
    d_lo, d_hi = first - lc, hf - last
    ok_lo = (d_lo <= 1e-9 and d_lo >= -1e-9) if lo["strike_type"] == "less" else (-1e-9 <= d_lo <= g + 1e-9)
    ok_hi = (abs(d_hi) <= 1e-9) if hi["strike_type"] == "greater" else (-1e-9 <= d_hi <= g + 1e-9)
    if not ok_lo or not ok_hi:
        return False, "colas_desalineadas"
    return True, "ok"


# ---------------------------------------------------------------------------------------------
# Estrategias
# ---------------------------------------------------------------------------------------------
def _row(e, ts, kind, legs, cost, payout, days, cov=""):
    prof = payout - cost
    ret = prof / cost if cost and np.isfinite(cost) else np.nan
    ann = ret * 365 / days if np.isfinite(ret) and days and np.isfinite(days) else np.nan
    return {"ts": ts.isoformat(), "event_ticker": e.get("event_ticker"), "series_ticker": e.get("series_ticker"),
            "category": e.get("category"), "title": (e.get("title") or "")[:80], "kind": kind, "coverage": cov,
            "n_legs": len(legs), "legs": "|".join(legs), "cost": cost, "payout": payout, "profit": prof,
            "ret": ret, "days": days, "ann": ann,
            "opp": bool(np.isfinite(ret) and ret >= MIN_RET and np.isfinite(ann) and ann >= MIN_ANN)}


def mutually_exclusive(e, bk, ts, c=C):
    """Filas me_no (siempre) y me_yes (solo con cobertura verificada y no activos liquidados en NO)."""
    if not e.get("mutually_exclusive"):
        return []
    ms = active(e)
    if len(ms) < 2:
        return []
    days = _days(ms, ts)
    rows = []
    cno = sum(leg_cost(bk.get(m["ticker"]), "no", c) for m in ms)
    rows.append(_row(e, ts, "me_no", [m["ticker"] + ":no" for m in ms], cno, c * (len(ms) - 1), days))
    ok, why = coverage(e.get("markets") or [])
    rest_no = all((m.get("result") or "") == "no" for m in e.get("markets") or [] if m.get("status") != "active")
    if ok and not rest_no:
        ok, why = False, "inactivo_no_liquidado_no"
    rows[0]["coverage"] = why
    if ok:
        cyes = sum(leg_cost(bk.get(m["ticker"]), "yes", c) for m in ms)
        rows.append(_row(e, ts, "me_yes", [m["ticker"] + ":yes" for m in ms], cyes, c, days, why))
    return rows


def _template(m):
    return NUM.sub("#", (m.get("rules_primary") or "")).strip().lower()


def ladder_pairs(e, bk, ts, c=C):
    """Todas las parejas de una escalera de strikes (evento no excluyente). Devuelve filas 'ladder'."""
    if e.get("mutually_exclusive"):
        return []
    ms = active(e)
    out = []
    for a, b in combinations(ms, 2):
        sa, sb = a.get("strike_type"), b.get("strike_type")
        if sa != sb or sa not in UP_T + DOWN_T:
            continue
        if a.get("close_time") != b.get("close_time") or _template(a) != _template(b):
            continue
        key = "floor_strike" if sa in UP_T else "cap_strike"
        ka, kb = _f(a.get(key)), _f(b.get(key))
        if ka is None or kb is None or ka == kb:
            continue
        lo, hi = (a, b) if ka < kb else (b, a)
        # above: {x>K1} ⊇ {x>K2} → YES(K1)+NO(K2); below: {x<K2} ⊇ {x<K1} → YES(K2)+NO(K1)
        y, n = (lo, hi) if sa in UP_T else (hi, lo)
        cost = leg_cost(bk.get(y["ticker"]), "yes", c) + leg_cost(bk.get(n["ticker"]), "no", c)
        out.append(_row(e, ts, "ladder", [y["ticker"] + ":yes", n["ticker"] + ":no"], cost, c, _days([y, n], ts)))
    return out


def analyse(e, bk, ts, c=C):
    """Mejor fila por (evento, tipo) + nº de parejas de escalera con beneficio > 0."""
    rows = mutually_exclusive(e, bk, ts, c)
    lp = ladder_pairs(e, bk, ts, c)
    if lp:
        fin = [r for r in lp if np.isfinite(r["ret"])]
        best = max(fin, key=lambda r: r["ret"]) if fin else lp[0]
        best = dict(best, n_pairs=len(lp), n_pos=sum(r["profit"] > 0 for r in fin))
        rows.append(best)
    return rows


# ---------------------------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------------------------
def snapshot():
    ts = pd.Timestamp.now(tz="UTC")
    evs = open_events()
    bk = books(evs)
    rows = [r for e in evs for r in analyse(e, bk, ts)]
    df = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    if len(df):
        p = os.path.join(OUT, "opps.csv")
        cols = list(_row({}, ts, "", [], 1.0, 1.0, 1.0)) + ["n_pairs", "n_pos"]
        df.reindex(columns=cols).to_csv(p, mode="a", header=not os.path.exists(p), index=False)
        hit = set(df.loc[df.profit > 0, "event_ticker"])
        with gzip.open(os.path.join(OUT, f"snap_{ts:%Y%m%dT%H%M}.jsonl.gz"), "wt") as f:
            for e in (e for e in evs if e["event_ticker"] in hit):
                f.write(json.dumps({"event": {k: v for k, v in e.items() if k != "markets"},
                                    "markets": e.get("markets"),
                                    "books": {m["ticker"]: bk.get(m["ticker"]) for m in active(e)}}) + "\n")
    nmk = sum(len(active(e)) for e in evs)
    nme = sum(bool(e.get("mutually_exclusive")) for e in evs)
    nyes = int((df.kind == "me_yes").sum()) if len(df) else 0
    nopp = df[df.opp].event_ticker.nunique() if len(df) else 0
    best = df.ret.max() if len(df) else np.nan
    print(f"{ts:%Y-%m-%d %H:%M} eventos={len(evs)} mercados={nmk} libros={len(bk)} excluyentes={nme} "
          f"cobertura_ok={nyes} filas={len(df)} eventos_opp={nopp} mejor_ret={best:.4f}", flush=True)
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--loop", type=float, default=0); a = ap.parse_args()
    while True:
        try:
            snapshot()
        except Exception as ex:  # un snapshot fallido no debe parar la serie
            print("ERROR", repr(ex)[:200], flush=True)
        if not a.loop:
            break
        time.sleep(a.loop * 60)
