"""H033 — P(presidencia 2028) ≤ P(nominación). Snapshots forward.
Uso: PYTHONPATH=src python -m pmq.h033 [--loop MINUTOS] → data/h033/opps.csv"""
import argparse, json, os, re, time
import pandas as pd
import requests

from pmq.h002 import books, buy_cost, fee_rate
from pmq.universe import DATA

OUT = os.path.join(DATA, "h033")
PRES, NOMS = "presidential-election-winner-2028", ["democratic-presidential-nominee-2028", "republican-presidential-nominee-2028"]
RP = re.compile(r"^Will (.+) win the 2028 US Presidential Election\?$")
RN = re.compile(r"^Will (.+) win the 2028 (?:Democratic|Republican) presidential nomination\?$")
SIZE = 50
ELECTION = pd.Timestamp("2028-11-07", tz="UTC")


def markets(slug):
    d = requests.get("https://gamma-api.polymarket.com/events", params={"slug": slug}, timeout=60).json()
    return [m for e in d for m in e.get("markets") or [] if m.get("acceptingOrders") and not m.get("closed")]


def pair(pres, noms):
    """Empareja por nombre exacto del candidato. Devuelve lista (nombre, mercado_pres, mercado_nom)."""
    p = {RP.match(m["question"]).group(1): m for m in pres if RP.match(m.get("question") or "")}
    n = {RN.match(m["question"]).group(1): m for m in noms if RN.match(m.get("question") or "")}
    return [(k, p[k], n[k]) for k in sorted(set(p) & set(n))]


def snapshot():
    ts = pd.Timestamp.now(tz="UTC")
    ps = pair(markets(PRES), [m for s in NOMS for m in markets(s)])
    bk = books([t for _, a, b in ps for t in json.loads(a["clobTokenIds"]) + json.loads(b["clobTokenIds"])])
    rows = []
    for name, a, b in ps:
        ta, tb = json.loads(a["clobTokenIds"]), json.loads(b["clobTokenIds"])
        cost = buy_cost(bk.get(ta[1]), SIZE, fee_rate(a)) + buy_cost(bk.get(tb[0]), SIZE, fee_rate(b))
        days = (ELECTION - ts).total_seconds() / 86400
        ret = (SIZE - cost) / cost
        rows.append({"ts": ts.isoformat(), "name": name, "cost": cost, "ret": ret, "ann": ret * 365 / days})
    os.makedirs(OUT, exist_ok=True)
    df = pd.DataFrame(rows)
    p = os.path.join(OUT, "opps.csv")
    df.to_csv(p, mode="a", header=not os.path.exists(p), index=False)
    print(f"{ts:%Y-%m-%d %H:%M} pares={len(df)} ret>0={int((df.ret > 0).sum()) if len(df) else 0}", flush=True)
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--loop", type=float, default=0); a = ap.parse_args()
    while True:
        try:
            snapshot()
        except Exception as e:
            print("ERROR", repr(e)[:200], flush=True)
        if not a.loop:
            break
        time.sleep(a.loop * 60)
