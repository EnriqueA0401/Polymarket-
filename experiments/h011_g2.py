"""H011 G2 (solo entrenamiento; series 15m y hourly — 5m excluidas en G1 por concordancia < 97%).
python experiments/h011_g2.py → reports/h011_g2.md"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h005, h011, trades
from pmq.universe import DATA

THETA, LAT0, LAT1 = 0.03, 30, 90
s = pd.read_parquet(os.path.join(DATA, "h011_sample.parquet"))
s = s[~s.series.str.endswith("-5m")].copy()
kl = {sym: h011.load_klines(sym, pd.date_range(g.t0.min().normalize() - pd.Timedelta("1D"), g.t0.max().normalize(), freq="D"))
      for sym, g in s.groupby("sym")}
rows = []
for r in s.itertuples():
    k = kl[r.sym]
    half = r.win // 2
    dec = r.t0 + pd.Timedelta(minutes=half)                     # instante de decisión s
    past = k.loc[dec - pd.Timedelta(minutes=61): dec - pd.Timedelta(minutes=1)]   # minutos cerrados < s
    if len(past) < 50 or r.t0 not in k.index:
        continue
    S0, S = k.loc[r.t0, "open"], past.close.iloc[-1]
    sig = h011.sigma_1m(past.close.values)
    p = h011.fair_candle(S0, S, r.win - half, sig)
    rows.append({"id": r.id, "cid": r.condition_id, "series": r.series, "y": r.y, "clean": r.clean,
                 "dec": int(dec.timestamp()), "fair": p, "t0": r.t0, "rate": h001.fee_rate(r.fee_schedule)})
d = pd.DataFrame(rows)
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda x: trades.fetch(x[0], x[1] + LAT0, x[1] + LAT1, os.path.join(DATA, "trades_h011")),
                      zip(d.cid, d.dec)))
d["px_yes"] = [h005.exec_price(r, 0, t + LAT0, t + LAT1) for r, t in zip(res, d.dec)]
d["px_no"] = [h005.exec_price(r, 1, t + LAT0, t + LAT1) for r, t in zip(res, d.dec)]
dec_ = [h005.decide(f, py, pn, rt, THETA) for f, py, pn, rt in zip(d.fair, d.px_yes, d.px_no, d.rate)]
d["side"], d["px"], d["edge"] = zip(*dec_)
b = d[d.side.notna()].copy()
b["pnl"] = [h005.pnl(sd, px, rt, y) for sd, px, rt, y in zip(b.side, b.px, b.rate, b.y)]
b["cl"] = b.t0.dt.floor("h").astype(str)
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = ["# H011 G2 — cripto Up/Down vs Binance (solo entrenamiento)", "", f"- commit {commit}",
     f"- mercados evaluados {len(d):,}; con trades YES en ventana {d.px_yes.notna().sum():,}, NO {d.px_no.notna().sum():,}", ""]
for name, g in [("TODAS", b)] + list(b.groupby("series")):
    lo, hi = h001.cluster_bootstrap(g, col="pnl", cluster="cl") if len(g) > 20 else (np.nan, np.nan)
    L.append(f"- {name}: apuestas {len(g):,}; PnL {g.pnl.mean()*100:.3f} c/acción (IC95% {lo*100:.3f} … {hi*100:.3f}); "
             f"edge esperado {g.edge.mean()*100:.2f} c; precio medio {g.px.mean():.3f}")
mk = d[d.px_yes.notna()]
L += ["", f"- Diagnóstico Brier (n={len(mk):,}): modelo {((mk.fair-mk.y)**2).mean():.4f} vs PM peor compra YES {((mk.px_yes-mk.y)**2).mean():.4f}"]
open(os.path.join(ROOT, "reports", "h011_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
