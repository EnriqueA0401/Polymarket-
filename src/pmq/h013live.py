"""H013 etapa 2b — paper trading de un maker pequeño en mercados con recompensas.

Uso: PYTHONPATH=src python -m pmq.h013live [--init] [--loop MINUTOS]
Estado persistente (reanudable tras reinicios): data/h013/live/state.json
Registro por intervalo: data/h013/live/log.csv
"""
import argparse, json, os, time
import numpy as np
import pandas as pd
import requests

from pmq import h013, trades
from pmq.h002 import books
from pmq.universe import DATA

LIVE = os.path.join(DATA, "h013", "live")
STATE = os.path.join(LIVE, "state.json")
N_MARKETS, STEP = 60, 300


def crossed(tr, bid, ask):
    """(hit_bid, hit_ask): algún trade taker cruza ESTRICTAMENTE nuestra puja YES o nuestra oferta YES
    (incluye el libro complementario NO)."""
    hb = any((x["outcomeIndex"] == 0 and x["side"] == "SELL" and float(x["price"]) < bid) or
             (x["outcomeIndex"] == 1 and x["side"] == "BUY" and float(x["price"]) > 1 - bid) for x in tr)
    ha = any((x["outcomeIndex"] == 0 and x["side"] == "BUY" and float(x["price"]) > ask) or
             (x["outcomeIndex"] == 1 and x["side"] == "SELL" and float(x["price"]) < 1 - ask) for x in tr)
    return hb, ha


def settle(m, y):
    """PnL a resolución de las posiciones acumuladas (y = pago YES)."""
    return m["pos_yes"] * y - m["cost_yes"] + m["pos_no"] * (1 - y) - m["cost_no"]


def init():
    ms = h013.rewarded_markets()
    now = pd.Timestamp.now(tz="UTC")
    rows = []
    for m in ms:
        rw = m.get("rewards") or {}
        rate = sum(float(c.get("rewards_daily_rate") or 0) for c in rw.get("rates") or [])
        tk = [t["token_id"] for t in m.get("tokens") or []]
        end = pd.to_datetime(m.get("end_date_iso"), utc=True, errors="coerce")
        if len(tk) != 2 or rate < 5 or pd.isna(end) or not (now + pd.Timedelta("2D") <= end <= now + pd.Timedelta("10D")):
            continue
        if not rw.get("max_spread") or not rw.get("min_size") or not m.get("accepting_orders"):
            continue
        rows.append({"cid": m["condition_id"], "q": m.get("question"), "rate": rate, "v": float(rw["max_spread"]) / 100,
                     "min_size": float(rw["min_size"]), "yes": tk[0], "no": tk[1], "end": end.isoformat()})
    df = pd.DataFrame(rows)
    bk = books(list(df.yes) + list(df.no))
    mids = []
    for r in df.itertuples():
        b = h013.merge(bk.get(r.yes), bk.get(r.no))
        if not b or not b["bids"] or not b["asks"]:
            mids.append(np.nan); continue
        mids.append((max(float(x["price"]) for x in b["bids"]) + min(float(x["price"]) for x in b["asks"])) / 2)
    df["mid0"] = mids
    df = df[(df.mid0 >= .15) & (df.mid0 <= .85)].sample(frac=1, random_state=0).head(N_MARKETS)
    st = {"created": now.isoformat(), "last": int(now.timestamp()), "candidates": len(rows),
          "markets": {r.cid: {**{k: getattr(r, k) for k in ("q", "rate", "v", "min_size", "yes", "no", "end")},
                              "quotes": None, "pos_yes": 0.0, "cost_yes": 0.0, "pos_no": 0.0, "cost_no": 0.0,
                              "reward": 0.0, "fills_bid": 0, "fills_ask": 0, "max_capital": 0.0, "done": False}
                      for r in df.itertuples()}}
    os.makedirs(LIVE, exist_ok=True)
    json.dump(st, open(STATE, "w"), indent=1)
    print(f"init: {len(rows)} candidatos, {len(st['markets'])} seleccionados", flush=True)


def step():
    st = json.load(open(STATE))
    now = int(time.time())
    t0 = st["last"]
    act = {c: m for c, m in st["markets"].items() if not m["done"]}
    bk = books([m["yes"] for m in act.values()] + [m["no"] for m in act.values()])
    log = []
    for cid, m in act.items():
        # 1) fills del intervalo (t0, now] contra las cotizaciones vigentes desde t0
        q = m["quotes"]
        if q:
            tr = trades.fetch(cid, t0 + 1, now, os.path.join(LIVE, "trades")) or []
            hb, ha = crossed(tr, q["bid"], q["ask"])
            if hb:
                m["pos_yes"] += m["min_size"]; m["cost_yes"] += m["min_size"] * q["bid"]; m["fills_bid"] += 1
            if ha:   # vender YES a ask ≡ comprar NO a 1−ask
                m["pos_no"] += m["min_size"]; m["cost_no"] += m["min_size"] * (1 - q["ask"]); m["fills_ask"] += 1
            # 2) recompensa devengada en el intervalo con la cuota observada al inicio
            if q["reward_day"] >= 1:
                m["reward"] += q["reward_day"] * (now - t0) / 86400
        # 3) nuevas cotizaciones
        b = h013.merge(bk.get(m["yes"]), bk.get(m["no"]))
        e = h013.expected(b, m["rate"], m["v"] * 100, m["min_size"]) if b else None
        if pd.Timestamp(m["end"]) <= pd.Timestamp(now, unit="s", tz="UTC") or not e:
            m["quotes"] = None
            if pd.Timestamp(m["end"]) <= pd.Timestamp(now, unit="s", tz="UTC"):
                m["done"] = True
        else:
            m["quotes"] = {"bid": e["mid"] - m["v"] / 2, "ask": e["mid"] + m["v"] / 2, "reward_day": e["reward_day"],
                           "share": e["share"]}
            m["max_capital"] = max(m["max_capital"], m["cost_yes"] + m["cost_no"] + e["capital"])
        log.append({"ts": now, "cid": cid, "mid": e["mid"] if e else np.nan, "share": e["share"] if e else np.nan,
                    "reward": m["reward"], "fills_bid": m["fills_bid"], "fills_ask": m["fills_ask"]})
    st["last"] = now
    tmp = STATE + ".tmp"
    json.dump(st, open(tmp, "w"), indent=1)
    os.replace(tmp, STATE)
    p = os.path.join(LIVE, "log.csv")
    pd.DataFrame(log).to_csv(p, mode="a", header=not os.path.exists(p), index=False)
    print(f"{pd.Timestamp(now, unit='s')} activos={len(act)} recompensa_acum={sum(m['reward'] for m in st['markets'].values()):.2f}",
          flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--loop", type=float, default=0)
    a = ap.parse_args()
    if a.init or not os.path.exists(STATE):
        init()
    while True:
        try:
            step()
        except Exception as e:
            print("ERROR", repr(e)[:200], flush=True)
        if not a.loop:
            break
        time.sleep(a.loop * 60)
