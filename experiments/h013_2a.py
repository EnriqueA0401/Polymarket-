"""H013 etapa 2a (entrenamiento): selección adversa de un maker a mid ± v/2 vs recompensa máxima.
python experiments/h013_2a.py → reports/h013_2a.md"""
import glob, gzip, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd, requests
from pmq import h001, h013sim, trades
from pmq.universe import DATA, parse

SCAN = os.path.join(DATA, "h013_scan.parquet")
if not os.path.exists(SCAN):
    rows = []
    for f in sorted(glob.glob(os.path.join(DATA, "gamma", "win_2025-*.jsonl.gz")) +
                    glob.glob(os.path.join(DATA, "gamma", "win_2026-0[1-4]*.jsonl.gz"))):
        for l in gzip.open(f, "rt"):
            if '"rewardsDailyRate"' not in l:
                continue
            m = json.loads(l)
            cr = [c for c in m.get("clobRewards") or [] if float(c.get("rewardsDailyRate") or 0) > 0]
            r = parse(m)
            if not cr or not r or not m.get("rewardsMaxSpread") or not m.get("rewardsMinSize"):
                continue
            r.update(rate=sum(float(c["rewardsDailyRate"]) for c in cr), v=float(m["rewardsMaxSpread"]) / 100,
                     min_size=float(m["rewardsMinSize"]), condition_id=m.get("conditionId"),
                     rw_start=min(c.get("startDate") or "9999" for c in cr))
            rows.append(r)
    pd.DataFrame(rows).drop_duplicates("id").to_parquet(SCAN)
s = pd.read_parquet(SCAN)
s = s[(s.closed_time < h001.HOLDOUT_START) & s.clean & s.end.notna()]
s = s[pd.to_datetime(s.rw_start, utc=True, errors="coerce") <= s.end - pd.Timedelta("48h")]
s = s[s.closed_time > s.end - pd.Timedelta("24h")]
s = s.sample(frac=1, random_state=0)


def mids(tok, a, b):
    for i in range(5):
        try:
            r = requests.get("https://clob.polymarket.com/prices-history",
                             params={"market": tok, "startTs": a - 3600, "endTs": b, "fidelity": 1}, timeout=60)
            if r.status_code == 200:
                return r.json().get("history", [])
        except requests.RequestException:
            pass
        time.sleep(2 ** i)
    return None


res = []
for r in s.itertuples():
    if len(res) >= 300:
        break
    a, b = int((r.end - pd.Timedelta("48h")).timestamp()), int((r.end - pd.Timedelta("24h")).timestamp())
    h = mids(r.token_yes, a, b)
    if not h:
        continue
    h = sorted(h, key=lambda x: x["t"])
    grid, j, last = [], 0, None
    for t in range(a, b, 60):
        while j < len(h) and h[j]["t"] <= t:
            last = h[j]["p"]; j += 1
        if last is not None:
            grid.append((t, last))
    if not grid or not (0.10 <= grid[0][1] <= 0.90):
        continue
    tr = trades.fetch(r.condition_id, a, b + 60, os.path.join(DATA, "trades_h013"))
    if tr is None:
        continue
    pnl, nb, na = h013sim.simulate(grid, tr, r.v, r.min_size, r.y)
    res.append({"id": r.id, "event_id": r.event_id, "rate": r.rate, "v": r.v, "min_size": r.min_size,
                "pnl": pnl, "fills_bid": nb, "fills_ask": na, "minutes": len(grid)})
d = pd.DataFrame(res)
d["net_max"] = d.pnl + d.rate                      # PnL del día + recompensa máxima (cuota 100%)
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = ["# H013 etapa 2a — selección adversa vs recompensa máxima (entrenamiento)", "", f"- commit {commit}",
     f"- mercados con recompensas (escaneo): {len(pd.read_parquet(SCAN)):,}; simulados: {len(d)} "
     f"({d.event_id.nunique()} eventos)",
     f"- fills medios por día: bid {d.fills_bid.mean():.1f}, ask {d.fills_ask.mean():.1f}",
     f"- PnL de cotización por día: mediana {d.pnl.median():.2f} USD, media {d.pnl.mean():.2f} USD",
     f"- recompensa máxima por día: mediana {d.rate.median():.2f} USD",
     f"- PnL + recompensa máxima: mediana {d.net_max.median():.2f} USD; fracción > 0: {(d.net_max > 0).mean():.1%}",
     f"- pérdida > recompensa máxima en la mediana: {'SÍ → rechazar' if (-d.pnl).median() > d.rate.median() else 'NO → etapa 2b (forward)'}"]
open(os.path.join(ROOT, "reports", "h013_2a.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
