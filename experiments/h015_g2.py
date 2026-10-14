"""H015 G2 (entrenamiento). python experiments/h015_g2.py → reports/h015_g2.md"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h004, h005, h015, trades
from pmq.universe import DATA

m = pd.read_parquet(os.path.join(DATA, "h005_matches.parquet"))
m = m[m.closed_time < h001.HOLDOUT_START].copy()
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=["id", "fee_schedule"])
m = m.merge(u, on="id")
m["t"] = m.kickoff + h015.AFTER
m = m[m.closed_time > m.t]                                   # el mercado sigue abierto en t (conocido en t)
m["t0"] = [int(x.timestamp()) for x in m.t]
m["idx"] = [h015.winner_idx(f, s) for f, s in zip(m.FTR, m.side)]
m["rate"] = [h001.fee_rate(x) for x in m.fee_schedule]
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda r: trades.fetch(r[0], r[1], r[1] + h015.WINDOW, os.path.join(DATA, "trades_h015")),
                      zip(m.condition_id, m.t0)))
m["px"] = [h005.exec_price(r, i, t, t + h015.WINDOW) for r, i, t in zip(res, m.idx, m.t0)]
b = m[m.px.notna() & (m.px <= h015.MAXPX)].copy()
b["pnl"] = [h004.pnl(i, p, rt, y) for i, p, rt, y in zip(b.idx, b.px, b.rate, b.y)]
b["hours"] = ((b.closed_time - b.t).dt.total_seconds() / 3600).clip(lower=0.25)
b["ret"] = b.pnl / b.px
b["ann"] = (1 + b.ret) ** (8760 / b.hours) - 1
pay = np.where(b.idx == 0, b.y, 1 - b.y)
lo, hi = h001.cluster_bootstrap(b.assign(match=b.fd_idx), col="pnl", cluster="match") if len(b) else (np.nan, np.nan)
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = ["# H015 G2 — ganador tras el partido (entrenamiento)", "", f"- commit {commit}",
     f"- mercados abiertos en t=kickoff+3h: {len(m):,}; con compra real del ganador en (t, t+2h]: {m.px.notna().sum():,}; "
     f"con precio ≤ {h015.MAXPX}: {len(b):,} ({b.fd_idx.nunique():,} partidos)",
     f"- precio medio {b.px.mean():.4f}; mediana {b.px.median():.4f}; horas medianas hasta cierre {b.hours.median():.2f}",
     f"- PnL medio {b.pnl.mean()*100:.3f} c/acción (IC95% cluster {lo*100:.3f} … {hi*100:.3f}); retorno medio {b.ret.mean():.3%}",
     f"- rendimiento anualizado mediano {b.ann.median():.1%}",
     f"- casos en que el 'ganador' NO cobró: {int((pay < 1).sum())} (anulados {int((b.y == 0.5).sum())})",
     f"- volumen disponible: mediana de compras taker del ganador en la ventana: "
     f"{np.median([sum(1 for x in (r or []) if x['outcomeIndex']==i and x['side']=='BUY') for r, i in zip(res, m.idx)]):.0f} trades", ""]
open(os.path.join(ROOT, "reports", "h015_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
