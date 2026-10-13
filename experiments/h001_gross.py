"""H001 diagnóstico: borde bruto (sin spread ni comisión) en entrenamiento. Cuenta como 1 variante."""
import os, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(__file__))
import pandas as pd
from pmq import h001
from h001_g2 import load_histories, COLS
from pmq.universe import DATA

hist = load_histories()
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=COLS)
u = u[u.id.isin(hist.keys()) & (u.closed_time < h001.HOLDOUT_START)]
L = ["# H001 — borde bruto por acción (entrenamiento, coste 0)", ""]
for name, h in [("24h", pd.Timedelta("24h")), ("7d", pd.Timedelta("7D"))]:
    o = h001.observations(u, hist, h)
    o = o[(o.p <= .10) | (o.p >= .90)]
    yes = o.p >= .90
    edge = ((o.y - o.p).where(yes, (1 - o.y) - (1 - o.p)))   # pago − precio del token comprado
    o = o.assign(edge=edge)
    lo, hi = h001.cluster_bootstrap(o, col="edge")
    L.append(f"- {name}: n={len(o):,}, borde bruto medio {o.edge.mean()*100:.3f} c/acción "
             f"(IC95% {lo*100:.3f} … {hi*100:.3f}); coste supuesto ≈ 2 c + comisión ≈ 0.2–0.5 c")
open(os.path.join(ROOT, "reports", "h001_gross.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
