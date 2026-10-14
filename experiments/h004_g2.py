"""H004 G2 (solo entrenamiento). python experiments/h004_g2.py → reports/h004_g2.md"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
from pmq import h001, h004, h005, trades
from pmq.universe import DATA
from h001_g2 import load_histories, COLS

hist = {**load_histories("h001"), **load_histories("h006r")}
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=COLS + ["condition_id"])
u = u[u.id.isin(hist.keys()) & (u.closed_time < h001.HOLDOUT_START)]
cid = u.set_index("id").condition_id
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = ["# H004 G2 — favoritos casi decididos (solo entrenamiento)", "", f"- commit {commit}", ""]
for name, h in [("6h", pd.Timedelta("6h")), ("1h", pd.Timedelta("1h"))]:
    o = h001.observations(u, hist, h)
    o["idx"] = [h004.fav_side(p) for p in o.p]
    o = o[o.idx.notna()].copy(); o["idx"] = o.idx.astype(int)
    o["t1"] = [int(t.timestamp()) for t in o.t]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda r: trades.fetch(cid[r[0]], r[1] - 3600, r[1], os.path.join(DATA, "trades_h004")),
                          zip(o.id, o.t1)))
    o["px"] = [h005.exec_price(r, i, t - 3600, t) for r, i, t in zip(res, o.idx, o.t1)]
    b = o[[h004.tradable(x) for x in o.px]].copy()
    b["pnl"] = [h004.pnl(i, px, rt, y) for i, px, rt, y in zip(b.idx, b.px, b.fee_rate, b.y)]
    b["hours"] = ((b.close - b.t).dt.total_seconds() / 3600).clip(lower=1)
    lo, hi = h001.cluster_bootstrap(b, col="pnl") if len(b) else (np.nan, np.nan)
    pay = np.where(b.idx == 0, b.y, 1 - b.y)
    L += [f"## Horizonte {name}", "",
          f"- favoritos en t: {len(o):,}; ejecutables (precio real 0.95–0.995): {len(b):,} en {b.event_id.nunique():,} eventos",
          f"- PnL medio {b.pnl.mean()*100:.3f} c/acción (IC95% cluster {lo*100:.3f} … {hi*100:.3f}); "
          f"sin top-5 eventos {h004.drop_top(b)*100:.3f} c",
          f"- precio medio {b.px.mean():.4f}; tasa de acierto {(pay == 1).mean():.4f}; anulados {(b.y == 0.5).sum()}",
          f"- horas medianas hasta cierre {b.hours.median():.1f}",
          "- pérdidas de cola por categoría: " + ", ".join(f"{k}: {int(v)}" for k, v in
                                                        b[pay < 1].groupby(b.category.fillna('NA')).size().items()), ""]
open(os.path.join(ROOT, "reports", "h004_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
