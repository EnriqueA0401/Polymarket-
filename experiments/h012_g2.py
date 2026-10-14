"""H012 G2 (solo entrenamiento). python experiments/h012_g2.py → reports/h012_g2.md"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
from pmq import h001, h005, h012, trades
from pmq.universe import DATA
from h001_g2 import load_histories, COLS

hist = {**load_histories("h001"), **load_histories("h006r")}
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=COLS + ["condition_id"])
u = u[u.id.isin(hist.keys()) & (u.closed_time < h001.HOLDOUT_START)]
rows = []
for r in u.itertuples():
    j = h012.first_jump(hist[r.id], r.end.timestamp())
    if j and (pd.isna(r.closed_time) or r.closed_time.timestamp() > j[0] + 3900):
        rows.append({"id": r.id, "cid": r.condition_id, "event_id": r.event_id, "y": r.y, "t": j[0], "dir": j[1],
                     "p": j[2], "rate": h001.fee_rate(r.fee_schedule)})
s = pd.DataFrame(rows)
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda x: trades.fetch(x[0], x[1] + 300, x[1] + 3900, os.path.join(DATA, "trades_h012")),
                      zip(s.cid, s.t)))
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = ["# H012 G2 — reacción tras saltos ≥10 c (solo entrenamiento)", "", f"- commit {commit}",
     f"- saltos detectados: {len(s):,} en {s.event_id.nunique():,} eventos (suben {int((s.dir>0).sum())}, bajan {int((s.dir<0).sum())})", ""]
pv = []
for name, sign in [("A seguir", 1), ("B revertir", -1)]:
    idx = np.where(s.dir * sign > 0, 0, 1)            # 0 = comprar YES, 1 = comprar NO
    px = [h005.exec_price(r, i, t + 300, t + 3900) for r, i, t in zip(res, idx, s.t)]
    b = s.assign(idx=idx, px=px).dropna(subset=["px"])
    b = b[(b.px > 0.01) & (b.px < 0.99)]
    pay = np.where(b.idx == 0, b.y, 1 - b.y)
    b = b.assign(pnl=pay - b.px - b.rate * b.px * (1 - b.px))
    lo, hi = h001.cluster_bootstrap(b, col="pnl")
    se = b.groupby("event_id").pnl.mean().std() / np.sqrt(b.event_id.nunique())
    from math import erf, sqrt
    pval = 1 - 0.5 * (1 + erf((b.pnl.mean() / se) / sqrt(2)))     # unilateral, aprox. por eventos
    pv.append(pval)
    L.append(f"- {name}: {len(b):,} ops ({b.event_id.nunique():,} eventos); PnL {b.pnl.mean()*100:.3f} c "
             f"(IC95% {lo*100:.3f} … {hi*100:.3f}); p unilateral ≈ {pval:.4f}; precio medio {b.px.mean():.3f}")
L.append(f"- Holm (2 pruebas): umbral mínimo p < 0.025 → {'alguna significativa' if min(pv) < 0.025 else 'ninguna significativa'}")
open(os.path.join(ROOT, "reports", "h012_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
