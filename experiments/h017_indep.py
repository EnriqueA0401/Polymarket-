"""Independent double implementation of H017 (TRAINING only).

Spec: at t = end - 90d, buy NO (taker, worst observed price in (t-3d, t]) on markets
whose YES price at t is in [0.02, 0.10]. Hold to resolution.
Run: python experiments/h017_indep.py
"""
import gzip
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "h017_indep")
PCACHE = os.path.join(CACHE, "prices")
TCACHE = os.path.join(CACHE, "trades")
HOLDOUT = pd.Timestamp("2026-04-12", tz="UTC")
DAY = 86400
S = requests.Session()


def get_json(url, params, tries=6):
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (400, 404):
                return None
        except Exception:
            pass
        time.sleep(1.5 * 2 ** i)
    raise RuntimeError(f"failed {url} {params}")


def cached(path, fn):
    if os.path.exists(path):
        with gzip.open(path, "rt") as f:
            return json.load(f)
    data = fn()
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt") as f:
        json.dump(data, f)
    os.replace(tmp, path)
    return data


def price_history(token):
    def f():
        j = get_json("https://clob.polymarket.com/prices-history",
                     {"market": token, "interval": "max", "fidelity": 1440})
        return (j or {}).get("history", [])
    return cached(os.path.join(PCACHE, f"{token}.json.gz"), f)


def trades(cid, t):
    def f():
        out, off = [], 0
        while True:
            page = get_json("https://data-api.polymarket.com/trades",
                            {"market": cid, "takerOnly": "true", "start": t - 3 * DAY,
                             "end": t, "limit": 10000, "offset": off}) or []
            out += page
            if len(page) < 500 or off >= 10000:
                break
            off += len(page)
        return out
    return cached(os.path.join(TCACHE, f"{cid}_{t}.json.gz"), f)


def fee_rate(fs):
    try:
        return float(json.loads(fs)["rate"])
    except Exception:
        return 0.07


def main():
    os.makedirs(PCACHE, exist_ok=True)
    os.makedirs(TCACHE, exist_ok=True)
    u = pd.read_parquet(os.path.join(ROOT, "data", "universe_binary.parquet"))
    m = ((u.closed_time < HOLDOUT) & (u.enable_ob == True)
         & (u.start <= u.end - pd.Timedelta(days=120))
         & (u.closed_time > u.end - pd.Timedelta(days=90)))
    u = u[m].copy()
    u["t"] = ((u.end - pd.Timedelta(days=90)).astype("int64") // 10**6).astype(np.int64)
    assert u.closed_time.max() < HOLDOUT
    print("universe", len(u), file=sys.stderr)

    rows = list(u.itertuples())
    with ThreadPoolExecutor(16) as ex:
        hists = list(ex.map(lambda r: price_history(r.token_yes), rows))

    sig = []
    for r, h in zip(rows, hists):
        pts = [x for x in h if r.t - 3 * DAY <= x["t"] <= r.t]
        if not pts:
            continue
        p = max(pts, key=lambda x: x["t"])["p"]
        if 0.02 <= p <= 0.10:
            sig.append((r, p))
    print("signals", len(sig), file=sys.stderr)

    with ThreadPoolExecutor(8) as ex:
        trs = list(ex.map(lambda s: trades(s[0].condition_id, int(s[0].t)), sig))

    out = []
    for (r, p), tr in zip(sig, trs):
        px = [float(x["price"]) for x in tr
              if int(x["outcomeIndex"]) == 1 and x["side"] == "BUY"
              and r.t - 3 * DAY < int(x["timestamp"]) <= r.t]
        if not px:
            continue
        q = max(px)
        if q >= 0.999:
            continue
        fee = fee_rate(r.fee_schedule) * q * (1 - q)
        pnl = (1 - r.y) - q - fee
        days = max(1.0, (r.closed_time.timestamp() - r.t) / DAY)
        out.append(dict(id=r.id, event_id=r.event_id, p_yes=p, q=q, fee=fee, y=r.y,
                        pnl=pnl, days=days, ann=pnl / q * 365 / days,
                        category=r.category))
    df = pd.DataFrame(out)
    df.to_parquet(os.path.join(CACHE, "trades_result.parquet"))

    # cluster bootstrap over events
    rng = np.random.default_rng(0)
    g = df.groupby("event_id")["pnl"].agg(["sum", "count"])
    sums, cnts = g["sum"].to_numpy(), g["count"].to_numpy()
    k = len(g)
    bs = np.empty(2000)
    for i in range(2000):
        idx = rng.integers(0, k, k)
        bs[i] = sums[idx].sum() / cnts[idx].sum()
    lo, hi = np.percentile(bs, [2.5, 97.5])

    res = dict(universe=len(u), signals=len(sig), n=len(df), events=k,
               mean_pnl=df.pnl.mean(), ci_lo=lo, ci_hi=hi, mean_ann=df.ann.mean(),
               median_ann=df.ann.median(), mean_q=df.q.mean(), yes_rate=(df.y == 1).mean(),
               void=(df.y == 0.5).sum(), mean_fee=df.fee.mean(), mean_days=df.days.mean())
    lines = ["# H017 independent double implementation (training only)", "",
             "Command: `python experiments/h017_indep.py` (cache: data/h017_indep/)",
             "Spec implemented from the caller's description only; holdout (closed_time >= 2026-04-12) excluded.", "",
             "| metric | value |", "|---|---|"]
    for kk, v in res.items():
        lines.append(f"| {kk} | {v:.6g} |" if isinstance(v, float) else f"| {kk} | {v} |")
    lines += ["", "mean_pnl in USD per share (x100 = cents). CI: 95% percentile bootstrap, "
              "events resampled, 2000 resamples, seed 0, statistic = ratio of summed PnL to trade count."]
    with open(os.path.join(ROOT, "reports", "h017_indep.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps(res, default=float, indent=1))


if __name__ == "__main__":
    main()
