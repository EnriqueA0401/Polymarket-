"""H003 G2 (solo entrenamiento). python experiments/h003_g2.py → reports/h003_g2.md"""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(__file__))
import pandas as pd
from pmq import h001, h003
from pmq.universe import DATA
from h001_g2 import load_histories, COLS

hist = load_histories()
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=COLS + ["outcome0"])
u = u[u.id.isin(hist.keys()) & (u.closed_time < h001.HOLDOUT_START)]
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = ["# H003 G2 — sobreprecio de Yes (solo entrenamiento)", "", f"- commit {commit}", ""]
for name, h in [("24h", pd.Timedelta("24h")), ("7d", pd.Timedelta("7D"))]:
    obs = h003.observations(u, hist, h)
    L += [f"## Horizonte {name} (observaciones con negociación previa: {len(obs):,})", ""]
    for grp, g in [("Yes/No", obs[obs.yesno]), ("Control (otros nombres)", obs[~obs.yesno])]:
        m = g[(g.p >= .2) & (g.p <= .8) & g.clean]
        tr = h003.trades(g)
        lo, hi = h001.cluster_bootstrap(tr) if len(tr) else (float("nan"),) * 2
        tr2 = h003.trades(g, cost_mult=2)
        L += [f"### {grp}", "",
              f"- zona 0.2–0.8 (limpios): n={len(m):,}, precio medio {m.p.mean():.4f}, frecuencia YES {m.y.mean():.4f}, "
              f"diferencia {m.p.mean() - m.y.mean():+.4f}",
              f"- comprar NO: {len(tr):,} ops / {tr.event_id.nunique():,} eventos; ret neto {tr.ret.mean():.3%} "
              f"(IC95% cluster {lo:.3%} … {hi:.3%}); costes×2: {tr2.ret.mean():.3%}", ""]
open(os.path.join(ROOT, "reports", "h003_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
