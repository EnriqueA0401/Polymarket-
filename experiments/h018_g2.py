"""H018 G2 (entrenamiento): comprar NO en mercados de mención 2h antes de endDate.
python experiments/h018_g2.py → reports/h018_g2.md"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h004, h005, trades
from pmq.universe import DATA

u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                    columns=["id", "condition_id", "question", "event_id", "y", "end", "closed_time", "fee_schedule"])
m = u[u.question.str.contains(r"\b(?:say|mention)\b", case=False, regex=True, na=False) & (u.closed_time < h001.HOLDOUT_START)].copy()
m["t1"] = [int((e - pd.Timedelta("2h")).timestamp()) for e in m.end]
m = m[m.closed_time > m.end - pd.Timedelta("2h")]
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda r: trades.fetch(r[0], r[1] - 7200, r[1], os.path.join(DATA, "trades_h018")), zip(m.condition_id, m.t1)))
m["px"] = [h005.exec_price(r, 1, a - 7200, a) for r, a in zip(res, m.t1)]
b = m[m.px.notna() & (m.px >= 0.20) & (m.px <= 0.80)].copy()
b["rate"] = [h001.fee_rate(x) for x in b.fee_schedule]
b["pnl"] = [h004.pnl(1, p, r, y) for p, r, y in zip(b.px, b.rate, b.y)]
lo, hi = h001.cluster_bootstrap(b, col="pnl")
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = ["# H018 G2 — comprar NO en mercados de mención (entrenamiento)", "", f"- commit {commit}",
     f"- mercados {len(m):,}; con compra real de NO en (t−2h, t]: {m.px.notna().sum():,}; en zona 0.20–0.80: {len(b):,} "
     f"({b.event_id.nunique():,} eventos)",
     f"- PnL medio {b.pnl.mean()*100:.3f} c/acción (IC95% cluster {lo*100:.3f} … {hi*100:.3f}); sin top-5 eventos "
     f"{(lambda s_: b[~b.event_id.isin(s_.index[:5])].pnl.mean())(b.groupby('event_id').pnl.sum().sort_values(ascending=False))*100:.3f} c",
     f"- precio medio NO {b.px.mean():.3f}; frecuencia real de NO {(1 - b.y).mean():.3f}"]
open(os.path.join(ROOT, "reports", "h018_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
