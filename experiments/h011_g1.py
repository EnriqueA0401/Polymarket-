"""H011 G1: muestra de mercados Up/Down (BTC/ETH), regla de resolución y concordancia del proxy Binance.
python experiments/h011_g1.py → data/h011_sample.parquet, reports/h011_g1.md"""
import glob, gzip, json, os, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h011
from pmq.universe import DATA, parse

SERIES = {"btc-up-or-down-5m": ("BTCUSDT", "5m"), "btc-up-or-down-15m": ("BTCUSDT", "15m"),
          "btc-up-or-down-hourly": ("BTCUSDT", "hourly"), "eth-up-or-down-5m": ("ETHUSDT", "5m"),
          "eth-up-or-down-15m": ("ETHUSDT", "15m"), "eth-up-or-down-hourly": ("ETHUSDT", "hourly")}
rows = []
for f in sorted(glob.glob(os.path.join(DATA, "gamma", "win_2025-0[5-9]*.jsonl.gz")) +
                glob.glob(os.path.join(DATA, "gamma", "win_2025-1*.jsonl.gz")) +
                glob.glob(os.path.join(DATA, "gamma", "win_2026-0[1-4]*.jsonl.gz"))):
    for l in gzip.open(f, "rt"):
        if "Up or Down" not in l:
            continue
        m = json.loads(l)
        ev = (m.get("events") or [{}])[0]
        if ev.get("seriesSlug") not in SERIES:
            continue
        r = parse(m)
        if not r:
            continue
        d = m.get("description") or ""
        r.update(series=ev["seriesSlug"], rule="twap" if "TWAP" in d else "candle",
                 t0=pd.to_datetime(m.get("eventStartTime"), utc=True, errors="coerce"))
        rows.append(r)
s = pd.DataFrame(rows).drop_duplicates("id")
s = s[s.closed_time < h001.HOLDOUT_START]
s["sym"] = s.series.map(lambda x: SERIES[x][0]); s["win"] = s.series.map(lambda x: h011.WINDOW[SERIES[x][1]])
s["t0"] = s.t0.fillna(s.end - pd.to_timedelta(s.win, unit="m"))
s = s.groupby("series", group_keys=False).apply(lambda g: g.sample(min(3000, len(g)), random_state=0))
s.to_parquet(os.path.join(DATA, "h011_sample.parquet"))

def proxy(r, k):
    a, b = r.t0, r.t0 + pd.Timedelta(minutes=r.win)
    w = k.loc[a:b - pd.Timedelta(minutes=1)]
    if len(w) < r.win:
        return np.nan
    s0 = w.open.iloc[0]
    if r.rule == "twap":
        return float(w.close.mean() >= s0)
    return float(w.close.iloc[-1] >= s0)

L = ["# H011 G1 — muestra y concordancia proxy Binance vs resolución PM", "",
     f"- mercados en muestra: {len(s):,}", "- reglas: " + s.groupby(["series", "rule"]).size().to_string().replace("\n", "; "), ""]
out = []
for sym, g in s.groupby("sym"):
    days = pd.date_range(g.t0.min().normalize(), g.t0.max().normalize(), freq="D")
    k = h011.load_klines(sym, days)
    g = g.assign(proxy=[proxy(r, k) for r in g.itertuples()])
    out.append(g)
s = pd.concat(out)
s.to_parquet(os.path.join(DATA, "h011_sample.parquet"))
c = s[s.clean & s.proxy.notna()]
c = c.assign(ok=(c.proxy == c.y), month=c.t0.dt.strftime("%Y-%m"))
L += ["## Concordancia por serie", "", c.groupby(["series", "rule"]).ok.agg(["size", "mean"]).round(4).to_markdown(), "",
      "## Por mes (todas)", "", c.groupby("month").ok.agg(["size", "mean"]).round(4).to_markdown()]
open(os.path.join(ROOT, "reports", "h011_g1.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
