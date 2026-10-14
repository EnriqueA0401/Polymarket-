"""H026 — paper trading forward: carry en NO a ~90 d en mercados NO negRisk.

Uso: PYTHONPATH=src python -m pmq.h026 [--loop MINUTOS]
Registro: data/h026/signals.csv (una fila por mercado, primera señal).
"""
import argparse, json, os, time
import pandas as pd

from pmq.h002 import _get, books, buy_cost, fee_rate
from pmq.universe import DATA

OUT = os.path.join(DATA, "h026")
GM = "https://gamma-api.polymarket.com/markets/keyset"
SIZE = 50


def eligible(m, now):
    try:
        start = pd.to_datetime(m.get("startDate"), utc=True); end = pd.to_datetime(m.get("endDate"), utc=True)
        toks = json.loads(m.get("clobTokenIds") or "[]")
    except (ValueError, TypeError):
        return False
    return (len(toks) == 2 and not m.get("negRisk") and m.get("acceptingOrders") and not m.get("closed")
            and start <= end - pd.Timedelta("120D") and now + pd.Timedelta("80D") <= end <= now + pd.Timedelta("100D"))


def snapshot():
    now = pd.Timestamp.now(tz="UTC")
    ms, c = [], None
    while True:
        p = {"closed": "false", "limit": 100, "end_date_min": (now + pd.Timedelta("80D")).isoformat(),
             "end_date_max": (now + pd.Timedelta("100D")).isoformat()}
        if c:
            p["after_cursor"] = c
        d = _get(GM, p)
        ms += [m for m in d.get("markets") or [] if eligible(m, now)]
        c = d.get("next_cursor")
        if not c or not d.get("markets"):
            break
    path = os.path.join(OUT, "signals.csv")
    seen = set(pd.read_csv(path).id.astype(str)) if os.path.exists(path) else set()
    ms = [m for m in ms if str(m["id"]) not in seen]
    bk = books([t for m in ms for t in json.loads(m["clobTokenIds"])])
    rows = []
    for m in ms:
        y, n = json.loads(m["clobTokenIds"])
        b = bk.get(y)
        if not b or not b.get("bids") or not b.get("asks"):
            continue
        mid = (max(float(x["price"]) for x in b["bids"]) + min(float(x["price"]) for x in b["asks"])) / 2
        if not (0.02 <= mid <= 0.10):
            continue
        cost = buy_cost(bk.get(n), SIZE, fee_rate(m))
        if cost != cost:   # NaN: sin profundidad para 50 acciones
            continue
        rows.append({"ts": now.isoformat(), "id": m["id"], "cid": m.get("conditionId"), "q": (m.get("question") or "")[:90],
                     "event_id": (m.get("events") or [{}])[0].get("id"), "end": m["endDate"], "mid_yes": mid,
                     "cost50": cost, "px_no": cost / SIZE})
    os.makedirs(OUT, exist_ok=True)
    if rows:
        pd.DataFrame(rows).to_csv(path, mode="a", header=not os.path.exists(path), index=False)
    print(f"{now:%Y-%m-%d %H:%M} elegibles={len(ms)} nuevas_señales={len(rows)} total={len(seen) + len(rows)}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=float, default=0)
    a = ap.parse_args()
    while True:
        try:
            snapshot()
        except Exception as e:
            print("ERROR", repr(e)[:200], flush=True)
        if not a.loop:
            break
        time.sleep(a.loop * 60)


def portfolio_return(pnl, capital, days):
    """Rentabilidad anualizada de cartera: Σpnl / Σ(capital·días) · 365 (lección H024)."""
    import numpy as np
    pnl, capital, days = map(np.asarray, (pnl, capital, days))
    den = (capital * days).sum()
    return float(pnl.sum() / den * 365) if den > 0 else float("nan")
