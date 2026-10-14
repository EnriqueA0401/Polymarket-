"""H005 G2 (solo entrenamiento, closedTime < 2026-04-12). python experiments/h005_g2.py → reports/h005_g2.md"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h005, trades, football as F
from pmq.universe import DATA

m = pd.read_parquet(os.path.join(DATA, "h005_matches.parquet"))
m = m[m.clean & (m.closed_time < h001.HOLDOUT_START)].copy()
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=["id", "fee_schedule"])
m = m.merge(u, on="id")
fd = F.load_fd()
m["fair"] = [F.fair_prob({**fd.loc[i].to_dict(), "side": s}, "PS") for i, s in zip(m.fd_idx, m.side)]
m["fair_close"] = [F.fair_prob({**fd.loc[i].to_dict(), "side": s}, "PSC") for i, s in zip(m.fd_idx, m.side)]
m["rate"] = [h001.fee_rate(x) for x in m.fee_schedule]
m["t1"] = [int((k - pd.Timedelta("1h")).timestamp()) for k in m.kickoff]
m["t0"] = m.t1 - 3600
CACHE = os.path.join(DATA, "trades_h005")
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda r: trades.fetch(r[0], r[1], r[2], CACHE), zip(m.condition_id, m.t0, m.t1)))
m["px_yes"] = [h005.exec_price(r, 0, a, b) for r, a, b in zip(res, m.t0, m.t1)]
m["px_no"] = [h005.exec_price(r, 1, a, b) for r, a, b in zip(res, m.t0, m.t1)]
m["fail"] = [r is None for r in res]
d = [h005.decide(f, py, pn, rt) if pd.notna(f) else (None, np.nan, np.nan)
     for f, py, pn, rt in zip(m.fair, m.px_yes, m.px_no, m.rate)]
m["side_bet"], m["px"], m["edge"] = zip(*d)
b = m[m.side_bet.notna()].copy()
b["pnl"] = [h005.pnl(s, p, r, y) for s, p, r, y in zip(b.side_bet, b.px, b.rate, b.y)]
b["clv"] = np.where(b.side_bet == "YES", b.fair_close, 1 - b.fair_close) - b.px
b["match"] = b.fd_idx
lo, hi = h001.cluster_bootstrap(b, col="pnl", cluster="match") if len(b) else (np.nan, np.nan)
# Diagnóstico Brier en t: precio PM (último trade YES ejecutable) vs Pinnacle pre-partido
dg = m[m.px_yes.notna() & m.fair.notna()]
br_pm = ((dg.px_yes - dg.y) ** 2).mean(); br_ps = ((dg.fair - dg.y) ** 2).mean()
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = ["# H005 G2 — Polymarket vs Pinnacle pre-partido (solo entrenamiento)", "", f"- commit {commit}",
     f"- mercados entrenamiento emparejados: {len(m):,}; con prob. Pinnacle: {m.fair.notna().sum():,}; "
     f"fallos descarga trades: {int(m.fail.sum())}",
     f"- con trades ejecutables YES: {m.px_yes.notna().sum():,}; NO: {m.px_no.notna().sum():,}",
     f"- apuestas (edge ≥ {h005.THETA}): {len(b):,} en {b.match.nunique():,} partidos "
     f"(YES {int((b.side_bet=='YES').sum())}, NO {int((b.side_bet=='NO').sum())})",
     f"- PnL medio por acción {b.pnl.mean()*100:.3f} c (IC95% cluster {lo*100:.3f} … {hi*100:.3f}); "
     f"retorno medio {(b.pnl/b.px).mean():.3%}; edge medio esperado {b.edge.mean()*100:.2f} c",
     f"- CLV medio vs Pinnacle cierre: {b.clv.mean()*100:.3f} c; fracción CLV>0: {(b.clv>0).mean():.1%}",
     f"- Diagnóstico Brier (n={len(dg):,}): Polymarket (peor compra YES en t) {br_pm:.4f} vs Pinnacle pre-partido {br_ps:.4f}",
     ""]
open(os.path.join(ROOT, "reports", "h005_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
