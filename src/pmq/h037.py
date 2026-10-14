"""H037 — monotonía en escaleras de strikes. Uso: PYTHONPATH=src python -m pmq.h037 [--loop MIN]"""
import argparse, json, os, re, time
from itertools import combinations
import pandas as pd

from pmq.h002 import _get, books, buy_cost, fee_rate, GE
from pmq.universe import DATA

OUT = os.path.join(DATA, "h037")
SIZE = 50
UP = re.compile(r"\b(above|reach|hit|over|higher than|at least)\b", re.I)
DOWN = re.compile(r"\b(below|dip|dips|fall|falls|drop|drops|lower than)\b", re.I)
KRE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)\s*([kKmMbBtT])?")


def strike(q):
    m = KRE.search(q or "")
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    mult = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}.get((m.group(2) or "").lower(), 1)
    return v * mult


def template(q):
    return KRE.sub("$K", q or "").strip().lower()


def direction(q):
    """+1 si YES es más probable cuanto menor es K (above/reach/hit HIGH); −1 en el caso
    contrario (below/dip/hit LOW). Lo explícito "(LOW)/(HIGH)" manda sobre el verbo."""
    q = q or ""
    if re.search(r"\(low\)", q, re.I) or DOWN.search(q):
        return -1
    if re.search(r"\(high\)", q, re.I) or UP.search(q):
        return 1
    return 0


def pairs(ev, bk, ts):
    out = []
    ms = [m for m in ev.get("markets") or [] if m.get("acceptingOrders") and not m.get("closed") and m.get("clobTokenIds")]
    for a, b in combinations(ms, 2):
        if a.get("endDate") != b.get("endDate") or template(a["question"]) != template(b["question"]):
            continue
        d = direction(a["question"])
        ka, kb = strike(a["question"]), strike(b["question"])
        if d == 0 or ka is None or kb is None or ka == kb:
            continue
        lo, hi = (a, b) if ka < kb else (b, a)
        yes_m, no_m = (lo, hi) if d == 1 else (hi, lo)      # above: YES(K bajo)+NO(K alto)
        ty, tn = json.loads(yes_m["clobTokenIds"]), json.loads(no_m["clobTokenIds"])
        cost = buy_cost(bk.get(ty[0]), SIZE, fee_rate(yes_m)) + buy_cost(bk.get(tn[1]), SIZE, fee_rate(no_m))
        out.append({"ts": ts.isoformat(), "event_id": ev["id"], "q_yes": yes_m["question"][:80],
                    "q_no": no_m["question"][:80], "end": a.get("endDate"), "ret": (SIZE - cost) / cost})
    return out


def snapshot():
    ts = pd.Timestamp.now(tz="UTC")
    evs, c = [], None
    while True:
        p = {"closed": "false", "limit": 100}
        if c:
            p["after_cursor"] = c
        d = _get(GE, p)
        evs += [e for e in d.get("events") or [] if not e.get("negRisk") and len(e.get("markets") or []) >= 2
                and any(strike(m.get("question")) for m in e.get("markets") or [])]
        c = d.get("next_cursor")
        if not c or not d.get("events"):
            break
    toks = [t for e in evs for m in e["markets"] if m.get("acceptingOrders") and not m.get("closed") and m.get("clobTokenIds")
            for t in json.loads(m["clobTokenIds"])]
    bk = books(toks)
    df = pd.DataFrame([r for e in evs for r in pairs(e, bk, ts)])
    os.makedirs(OUT, exist_ok=True)
    if len(df):
        p = os.path.join(OUT, "opps.csv")
        df.to_csv(p, mode="a", header=not os.path.exists(p), index=False)
    print(f"{ts:%Y-%m-%d %H:%M} eventos={len(evs)} pares={len(df)} ret>=0.5%={int((df.ret >= .005).sum()) if len(df) else 0}", flush=True)


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
