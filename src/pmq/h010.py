"""H010 — escaleras de fechas límite ("¿X antes de D?") con precios incoherentes.

Uso: PYTHONPATH=src python -m pmq.h010 [--loop MINUTOS]
Salida: data/h010/opps.csv (una fila por par D1<D2 y snapshot) y crudos de pares con ret > 0.
"""
import argparse, gzip, json, os, time
from itertools import combinations
import pandas as pd

from pmq.h002 import _get, books, buy_cost, fee_rate, GE
from pmq.universe import DATA

OUT = os.path.join(DATA, "h010")
SIZE = 50


def ladder_events():
    evs, c = [], None
    while True:
        p = {"closed": "false", "limit": 100}
        if c:
            p["after_cursor"] = c
        d = _get(GE, p)
        for e in d.get("events") or []:
            if e.get("negRisk"):
                continue
            ms = [m for m in e.get("markets") or [] if m.get("acceptingOrders") and not m.get("closed")
                  and " by " in (m.get("question") or "") and m.get("endDate") and m.get("clobTokenIds")]
            if len({m["endDate"] for m in ms}) >= 2:
                evs.append({**e, "markets": ms})
        c = d.get("next_cursor")
        if not c or not d.get("events"):
            return evs


def subject(q):
    """Parte de la pregunta antes de ' by ' (lo que debe coincidir para que haya anidamiento)."""
    return (q or "").rsplit(" by ", 1)[0].strip().lower()


def pairs(ev, bk, ts):
    ms = sorted(ev["markets"], key=lambda m: m["endDate"])
    out = []
    for a, b in combinations(ms, 2):
        if a["endDate"] == b["endDate"] or subject(a.get("question")) != subject(b.get("question")):
            continue
        ta, tb = json.loads(a["clobTokenIds"]), json.loads(b["clobTokenIds"])
        cost = buy_cost(bk.get(ta[1]), SIZE, fee_rate(a)) + buy_cost(bk.get(tb[0]), SIZE, fee_rate(b))
        end = pd.to_datetime(b["endDate"], utc=True)
        days = max((end - ts).total_seconds() / 86400, 1 / 24)
        out.append({"ts": ts.isoformat(), "event_id": ev["id"], "title": (ev.get("title") or "")[:80],
                    "q1": (a.get("question") or "")[:80], "q2": (b.get("question") or "")[:80],
                    "d1": a["endDate"], "d2": b["endDate"], "days": days, "ret": (SIZE - cost) / cost})
    return out


def snapshot():
    ts = pd.Timestamp.now(tz="UTC")
    evs = ladder_events()
    tokens = [t for e in evs for m in e["markets"] for t in json.loads(m["clobTokenIds"])]
    bk = books(tokens)
    rows = [r for e in evs for r in pairs(e, bk, ts)]
    df = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "opps.csv")
    if len(df):
        df.to_csv(path, mode="a", header=not os.path.exists(path), index=False)
        hit = set(df.loc[df.ret > 0, "event_id"])
        with gzip.open(os.path.join(OUT, f"snap_{ts:%Y%m%dT%H%M}.jsonl.gz"), "wt") as f:
            for e in evs:
                if e["id"] in hit:
                    f.write(json.dumps({"event": e["id"], "markets": [{k: m.get(k) for k in (
                        "id", "question", "endDate", "clobTokenIds", "description")} for m in e["markets"]],
                        "books": {t: bk.get(t) for m in e["markets"] for t in json.loads(m["clobTokenIds"])}}) + "\n")
    print(f"{ts:%Y-%m-%d %H:%M} eventos={len(evs)} pares={len(df)} positivos={int((df.ret > 0).sum()) if len(df) else 0}",
          flush=True)


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
