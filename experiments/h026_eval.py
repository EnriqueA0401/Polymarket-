"""H026 evaluación G7 (paper trading). python experiments/h026_eval.py → reports/h026_g7.md"""
import json, os, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd, requests
from pmq import h001, h026
from pmq.universe import DATA

s = pd.read_csv(os.path.join(DATA, "h026", "signals.csv"))
res = {}
for cid in s.cid.unique():
    g = requests.get("https://gamma-api.polymarket.com/markets", params={"condition_ids": cid}, timeout=60).json()
    if g and g[0].get("closed"):
        px = [float(p) for p in json.loads(g[0].get("outcomePrices") or "[]")]
        res[cid] = (1.0 if px == [1.0, 0.0] else 0.0 if px == [0.0, 1.0] else 0.5,
                    pd.to_datetime(g[0].get("closedTime"), utc=True, errors="coerce"))
s["y"] = s.cid.map(lambda c: res.get(c, (np.nan, None))[0])
s["closed"] = s.cid.map(lambda c: res.get(c, (np.nan, pd.NaT))[1])
done_ev = s.groupby("event_id").y.apply(lambda v: v.notna().all())          # censura: eventos completos
r = s[s.event_id.map(done_ev) & s.y.notna()].copy()
r["pnl"] = (1 - r.y) * 50 - r.cost50
r["days"] = ((r.closed - pd.to_datetime(r.ts, utc=True)).dt.total_seconds() / 86400).clip(lower=1)
r["pnl_sh"] = r.pnl / 50
lo, hi = h001.cluster_bootstrap(r, col="pnl_sh") if len(r) > 5 else (np.nan, np.nan)
L = ["# H026 G7 — paper trading carry NO ~90 d (no negRisk)", "",
     f"- señales registradas {len(s)} ({s.event_id.nunique()} eventos); resueltas en eventos completos {len(r)} "
     f"({r.event_id.nunique()} eventos)",
     f"- PnL por acción {r.pnl_sh.mean()*100:.3f} c (IC95% por evento {lo*100:.3f} … {hi*100:.3f})" if len(r) else "- sin resueltos aún",
     f"- rentabilidad de cartera {h026.portfolio_return(r.pnl, r.cost50, r.days):.2%}/año" if len(r) else "",
     f"- criterio (≥50 resueltos, IC>0, cartera >6%): {'CUMPLE' if len(r) >= 50 and lo > 0 and h026.portfolio_return(r.pnl, r.cost50, r.days) > .06 else 'NO (aún)'}"]
open(os.path.join(ROOT, "reports", "h026_g7.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
