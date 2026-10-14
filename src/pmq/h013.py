"""H013 — recompensas de liquidez: rendimiento esperado de un maker pequeño (etapa 1).

Uso: PYTHONPATH=src python -m pmq.h013   → data/h013/snap_<ts>.csv
"""
import json, os, time
import pandas as pd
import requests

from pmq.h002 import books
from pmq.universe import DATA

OUT = os.path.join(DATA, "h013")


def rewarded_markets():
    out, cur = [], ""
    while cur != "LTE=":
        for i in range(6):
            try:
                r = requests.get("https://clob.polymarket.com/sampling-markets", params={"next_cursor": cur}, timeout=60)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(2 ** i)
        d = r.json()
        out += d.get("data") or []
        cur = d.get("next_cursor") or "LTE="
    return out


def side_score(levels, mid, v, buy):
    """Σ ((v−s)/v)²·tamaño de órdenes a distancia s < v del mid (s en precio, v en precio)."""
    q = 0.0
    for lv in levels or []:
        px, sz = float(lv["price"]), float(lv["size"])
        s = (mid - px) if buy else (px - mid)
        if 0 <= s < v:
            q += ((v - s) / v) ** 2 * sz
    return q


def merge(yes, no):
    """Libro YES combinado con el complemento: puja NO a q ≡ oferta YES a 1−q y viceversa
    (la competencia por recompensas incluye ambos libros; supuesto pesimista)."""
    if not yes:
        return None
    no = no or {}
    flip = lambda lv: [{"price": str(1 - float(x["price"])), "size": x["size"]} for x in lv or []]
    return {"bids": (yes.get("bids") or []) + flip(no.get("asks")),
            "asks": (yes.get("asks") or []) + flip(no.get("bids"))}


def expected(book, rate, v_cents, min_size):
    """Recompensa/día, capital y rendimiento para órdenes propias a v/2 en ambos lados."""
    if not book or not book.get("bids") or not book.get("asks") or min_size <= 0 or v_cents <= 0:
        return None
    bb = max(float(b["price"]) for b in book["bids"]); ba = min(float(a["price"]) for a in book["asks"])
    mid = (bb + ba) / 2
    if not (0.10 <= mid <= 0.90):
        return None
    v = v_cents / 100
    q = 0.25 * min_size                                   # ((v − v/2)/v)² = 0.25
    q1 = side_score(book["bids"], mid, v, True)
    q2 = side_score(book["asks"], mid, v, False)
    share = min(q / (q + q1), q / (q + q2))
    bid_px, ask_px = mid - v / 2, mid + v / 2
    capital = min_size * bid_px + min_size * (1 - ask_px)
    rew = rate * share
    return {"mid": mid, "spread": ba - bb, "share": share, "reward_day": rew, "capital": capital,
            "yield_day": rew / capital if capital > 0 else float("nan")}


def snapshot():
    ts = pd.Timestamp.now(tz="UTC")
    ms = rewarded_markets()
    rows, toks = [], []
    for m in ms:
        rw = m.get("rewards") or {}
        rate = sum(float(c.get("rewards_daily_rate") or 0) for c in rw.get("rates") or [])
        tk = [t["token_id"] for t in m.get("tokens") or []]
        if not tk or not rate:
            continue
        if len(tk) != 2:
            continue
        rows.append({"cid": m["condition_id"], "q": (m.get("question") or "")[:80], "rate": rate,
                     "v": float(rw.get("max_spread") or 0), "min_size": float(rw.get("min_size") or 0),
                     "tok": tk[0], "tok_no": tk[1]})
        toks += tk
    bk = books(toks)
    out = []
    for r in rows:
        e = expected(merge(bk.get(r["tok"]), bk.get(r["tok_no"])), r["rate"], r["v"], r["min_size"])
        if e:
            out.append({**r, **e, "ts": ts.isoformat()})
    df = pd.DataFrame(out)
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(os.path.join(OUT, f"snap_{ts:%Y%m%dT%H%M}.csv"), index=False)
    print(f"{ts:%Y-%m-%d %H:%M} recompensados={len(ms)} evaluables={len(df)}", flush=True)
    return df


if __name__ == "__main__":
    snapshot()
