"""H002 — arbitraje en eventos negRisk. Snapshot de libros vivos y cálculo de oportunidades.

Uso: PYTHONPATH=src python -m pmq.h002 [--loop MINUTOS]
Salida: data/h002/snap_<ts>.jsonl.gz (libros crudos por evento) y data/h002/opps.csv
(una fila por evento y snapshot, con métricas de los arbitrajes A y B).
"""
import argparse, gzip, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
import requests

from pmq.universe import DATA

OUT = os.path.join(DATA, "h002")
GE = "https://gamma-api.polymarket.com/events/keyset"
SIZES = (10, 50)  # acciones por pierna
DEFAULT_FEE_RATE = 0.07


def _get(url, params=None, json_body=None, tries=6):
    for i in range(tries):
        try:
            r = (requests.post(url, json=json_body, timeout=60) if json_body is not None
                 else requests.get(url, params=params, timeout=60))
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(min(2 ** i, 60))
    raise RuntimeError(f"fallo {url}")


def open_negrisk_events():
    evs, c = [], None
    while True:
        p = {"closed": "false", "limit": 100}
        if c:
            p["after_cursor"] = c
        d = _get(GE, p)
        evs += [e for e in d.get("events") or [] if e.get("negRisk")]
        c = d.get("next_cursor")
        if not c or not d.get("events"):
            return evs


def fee_rate(m):
    if not m.get("feesEnabled"):
        return 0.0
    try:
        return float(m["feeSchedule"]["rate"])
    except (KeyError, TypeError, ValueError):
        return DEFAULT_FEE_RATE


def books(tokens):
    out = {}
    chunks = [tokens[i:i + 100] for i in range(0, len(tokens), 100)]
    with ThreadPoolExecutor(4) as ex:
        for res in ex.map(lambda ch: _get("https://clob.polymarket.com/books",
                                          json_body=[{"token_id": t} for t in ch]), chunks):
            for b in res:
                out[b["asset_id"]] = b
    return out


def buy_cost(book, shares, rate):
    """Coste total (precio + comisión taker) de comprar `shares` barriendo asks. NaN si no hay profundidad."""
    if not book or not book.get("asks"):
        return np.nan
    asks = sorted((float(a["price"]), float(a["size"])) for a in book["asks"])
    left, cost = shares, 0.0
    for px, sz in asks:
        take = min(sz, left)
        cost += take * px + rate * take * px * (1 - px)
        left -= take
        if left <= 1e-9:
            return cost
    return np.nan


def sell_value(book, shares, rate):
    """Ingreso neto (precio − comisión taker) de vender `shares` barriendo bids. NaN si no hay profundidad."""
    if not book or not book.get("bids"):
        return np.nan
    bids = sorted(((float(b["price"]), float(b["size"])) for b in book["bids"]), reverse=True)
    left, val = shares, 0.0
    for px, sz in bids:
        take = min(sz, left)
        val += take * px - rate * take * px * (1 - px)
        left -= take
        if left <= 1e-9:
            return val
    return np.nan


def conversion(ev, bk, ts, s=50):
    """H036: comprar s NO_i, convertir en s YES de cada j≠i (adapter negRisk) y venderlos al instante.
    Solo eventos no aumentados con todos los mercados activos (conversión limpia). Mejor i."""
    allm = ev.get("markets") or []
    ms = [m for m in allm if m.get("acceptingOrders") and not m.get("closed")]
    if len(ms) < 3 or len(ms) != len(allm) or ev.get("negRiskAugmented"):
        return None
    toks = [json.loads(m["clobTokenIds"]) for m in ms]
    rates = [fee_rate(m) for m in ms]
    sells = [sell_value(bk.get(t[0]), s, r) for t, r in zip(toks, rates)]
    best = None
    for i, (t, r) in enumerate(zip(toks, rates)):
        cost = buy_cost(bk.get(t[1]), s, r)
        rev = sum(v for j, v in enumerate(sells) if j != i)
        prof = rev - cost
        if np.isfinite(prof) and (best is None or prof > best[1]):
            best = (i, prof)
    if best is None:
        return None
    return {"ts": ts.isoformat(), "event_id": ev["id"], "title": (ev.get("title") or "")[:80],
            "n": len(ms), "best_i": best[0], "profit_50": best[1]}


def analyse(ev, bk, ts):
    ms = [m for m in ev.get("markets") or [] if m.get("acceptingOrders") and not m.get("closed")]
    allm = ev.get("markets") or []
    if len(ms) < 2:
        return None
    toks = [json.loads(m["clobTokenIds"]) for m in ms]
    rates = [fee_rate(m) for m in ms]
    end = pd.to_datetime(ev.get("endDate"), utc=True, errors="coerce")
    days = max((end - ts).total_seconds() / 86400, 1 / 24) if pd.notna(end) else np.nan
    # A solo es seguro si el evento no está aumentado (placeholders) y todos los mercados
    # inactivos ya resolvieron NO; si no, el ganador puede estar fuera de lo comprado.
    inactive = [m for m in allm if m not in ms]
    resolved_no = all((m.get("outcomePrices") or "") .replace(" ", "") == '["0","1"]' for m in inactive)
    safe_a = (not ev.get("negRiskAugmented")) and resolved_no
    row = {"ts": ts.isoformat(), "event_id": ev["id"], "title": (ev.get("title") or "")[:80], "safe_a": safe_a,
           "n_active": len(ms), "n_total": len(allm), "augmented": bool(ev.get("negRiskAugmented")),
           "days": days}
    for s in SIZES:
        ca = sum(buy_cost(bk.get(t[0]), s, r) for t, r in zip(toks, rates))
        cb = sum(buy_cost(bk.get(t[1]), s, r) for t, r in zip(toks, rates))
        row[f"A_ret_{s}"] = (s - ca) / ca                         # pago s si gana un activo
        row[f"B_ret_{s}"] = (s * (len(ms) - 1) - cb) / cb          # pago mínimo s(n-1)
    return row


def snapshot():
    ts = pd.Timestamp.now(tz="UTC")
    evs = open_negrisk_events()
    tokens = []
    for e in evs:
        for m in e.get("markets") or []:
            if m.get("acceptingOrders") and not m.get("closed") and m.get("clobTokenIds"):
                tokens += json.loads(m["clobTokenIds"])
    bk = books(tokens)
    rows = [r for r in (analyse(e, bk, ts) for e in evs) if r]
    df = pd.DataFrame(rows)
    conv = pd.DataFrame([c for c in (conversion(e, bk, ts) for e in evs) if c])
    if len(conv):
        os.makedirs(OUT, exist_ok=True)
        pc = os.path.join(OUT, "opps_conv.csv")
        conv.to_csv(pc, mode="a", header=not os.path.exists(pc), index=False)
    # Solo se guardan crudos los eventos con algún retorno > 0 (auditoría sin llenar el disco)
    hit = set(df.loc[(df.filter(like="_ret_") > 0).any(axis=1), "event_id"]) if len(df) else set()
    os.makedirs(OUT, exist_ok=True)
    with gzip.open(os.path.join(OUT, f"snap_{ts:%Y%m%dT%H%M}.jsonl.gz"), "wt") as f:
        for e in (e for e in evs if e["id"] in hit):
            f.write(json.dumps({"event": {k: e.get(k) for k in ("id", "title", "endDate", "negRiskAugmented")},
                                "markets": [{k: m.get(k) for k in ("id", "groupItemTitle", "clobTokenIds", "acceptingOrders",
                                                                   "closed", "outcomePrices", "feesEnabled", "feeSchedule")}
                                            for m in e.get("markets") or []],
                                "books": {t: bk.get(t) for m in e.get("markets") or [] if m.get("clobTokenIds")
                                          for t in json.loads(m["clobTokenIds"])}}) + "\n")
    path = os.path.join(OUT, "opps.csv")
    df.to_csv(path, mode="a", header=not os.path.exists(path), index=False)
    print(f"{ts:%Y-%m-%d %H:%M} eventos={len(rows)} tokens={len(tokens)} libros={len(bk)}", flush=True)
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=float, default=0)
    a = ap.parse_args()
    while True:
        try:
            snapshot()
        except Exception as e:  # un snapshot fallido no debe parar la serie
            print("ERROR", repr(e)[:200], flush=True)
        if not a.loop:
            break
        time.sleep(a.loop * 60)
