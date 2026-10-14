"""H016 G2 (solo entrenamiento, protocolo fijado en HYPOTHESES.md): barreras BTC/ETH vs reflexión.
Requiere experiments/h016_g1.py. python experiments/h016_g2.py → data/h016_g2.parquet, reports/h016_g2.md"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h005, h016, trades
from pmq.universe import DATA

TDIR = os.path.join(DATA, "trades_h016")
c = pd.read_parquet(os.path.join(DATA, "h016_g1.parquet"))
n_all = len(c)
c = c[c.group_ok].copy()
c["t"] = c.end - h016.LEAD
# filtros baratos conocidos en t (los repite evaluate); evita descargar trades inútiles
c = c[(c.start < c.t) & ~(c.closed_time <= c.t)].copy()
kl = {a: h016.load_hl(h016.SYMBOL[a], g.start.min().floor("D") - pd.Timedelta("8D"), g.end.max().ceil("D"))
      for a, g in c.groupby("asset")}

pre = []
for r in c.itertuples():
    hit, S, sig, cov = h016.state_at(kl[r.asset], r.X, r.direction, r.start, r.t)
    pre.append(not hit and np.isfinite(S) and np.isfinite(sig))
c = c[pre].copy()
ts = c.t.map(lambda x: int(x.timestamp()))
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda a: trades.fetch(a[0], a[1] - h016.ENTRY_WIN, a[1], TDIR), zip(c.condition_id, ts)))
c["n_fail"] = [r is None for r in res]

rows = []
for r, tr in zip(c.itertuples(), res):
    rate = h001.fee_rate(r.fee_schedule)
    e = h016.evaluate(r.X, r.direction, r.start, r.end, r.closed_time, kl[r.asset], tr, rate)
    t1 = int(e["t"].timestamp())
    med = None
    if e["side"] is not None:
        med = h016.median_buy(tr, 0 if e["side"] == "YES" else 1, t1 - h016.ENTRY_WIN, t1)
    rows.append(dict(id=r.id, event_id=r.event_id, asset=r.asset, direction=r.direction, grp=r.grp, series=r.series,
                     X=r.X, end=r.end, y=r.y, clean=r.clean, rate=rate, med=med, fetch_fail=tr is None, **e))
d = pd.DataFrame(rows)
d.to_parquet(os.path.join(DATA, "h016_g2.parquet"))

b = d[d.side.notna()].copy()
b["pnl"] = [h005.pnl(s, p, rt, y) for s, p, rt, y in zip(b.side, b.px, b.rate, b.y)]
# costes ×2: comisión ×2 y un slippage adicional = max(0.01, peor − mediana de compras en la ventana)
b["px2"] = np.minimum(b.px + np.maximum(0.01, b.px - b.med.astype(float)), 0.999)
b["pnl2"] = [h005.pnl(s, p, 2 * rt, y) for s, p, rt, y in zip(b.side, b.px2, b.rate, b.y)]
b["cl"] = b.end.dt.strftime("%Y-%m-%d") + "|" + b.asset
et = b.t.dt.tz_convert("America/New_York")
b["weekend"] = et.dt.dayofweek >= 5
b["fair_side"] = np.where(b.side == "YES", b.fair, 1 - b.fair)
b["payoff"] = np.where(b.side == "YES", b.y, 1 - b.y)


def line(name, g, col="pnl"):
    if len(g) == 0:
        return f"- {name}: 0 apuestas"
    lo, hi = h001.cluster_bootstrap(g, col=col, cluster="cl") if g.cl.nunique() > 1 else (np.nan, np.nan)
    return (f"- {name}: n={len(g):,} apuestas, {g.event_id.nunique():,} eventos, {g.cl.nunique():,} clusters; "
            f"PnL {g[col].mean()*100:+.2f} c/acción (IC95% cluster {lo*100:+.2f} … {hi*100:+.2f}); "
            f"precio medio {g.px.mean():.3f}; edge esperado {g.edge.mean()*100:.1f} c; acierto {g.payoff.mean():.3f} vs modelo {g.fair_side.mean():.3f}")


commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
why = d.why.fillna("APUESTA").value_counts()
L = ["# H016 G2 — barreras BTC/ETH vs reflexión (solo entrenamiento)", "",
     f"- commit {commit}; protocolo HYPOTHESES.md H016 (t = endDate − 3d, σ 7d 1m, entrada peor compra taker (t−1h, t], θ = 0.05). Variantes: 1.",
     f"- mercados G1 parseados {n_all:,}; en grupos que pasan G1 y abiertos en t sin toque previo con klines: {len(d):,}",
     f"- fallos de descarga de trades: {int(d.fetch_fail.sum())}",
     "- desenlace por mercado: " + "; ".join(f"{k} {v:,}" for k, v in why.items()), "",
     "## Resultado principal", "", line("TODAS", b), line("TODAS, costes ×2", b, "pnl2"), "",
     "## Estratos", ""]
for k, g in b.groupby("side"):
    L.append(line(f"lado {k}", g))
for k, g in b.groupby("asset"):
    L.append(line(f"activo {k}", g))
for k, g in b.groupby("direction"):
    L.append(line(f"dirección {k}", g))
for k, g in b.groupby("grp"):
    L.append(line(f"grupo {k}", g))
L += [line("fin de semana (t sáb/dom ET, estrato prefijado)", b[b.weekend]),
      line("entre semana", b[~b.weekend]), ""]
top = b.groupby("cl").pnl.sum().nlargest(5).index
L += ["## Sin los 5 mejores clusters", "", line("sin top-5", b[~b.cl.isin(top)]), ""]
# Brier modelo vs precio ejecutable (mercados con trade YES en la ventana, limpios)
m = d[d.px_yes.notna() & d.clean & d.fair.notna()].copy()
if len(m):
    m["cl"] = m.end.dt.strftime("%Y-%m-%d") + "|" + m.asset
    m["dB"] = (m.fair - m.y) ** 2 - (m.px_yes.astype(float) - m.y) ** 2
    lo, hi = h001.cluster_bootstrap(m, col="dB", cluster="cl")
    L += ["## Brier (limpios con compra YES en (t−1h, t])", "",
          f"- n={len(m):,}: modelo {((m.fair-m.y)**2).mean():.4f} vs peor compra YES {((m.px_yes.astype(float)-m.y)**2).mean():.4f}; "
          f"diferencia modelo−mercado {m.dB.mean():+.4f} (IC95% cluster {lo:+.4f} … {hi:+.4f}; < 0 = modelo mejor)",
          f"- calibración modelo: media P_toque {m.fair.mean():.3f} vs frecuencia {m.y.mean():.3f}; mercado {m.px_yes.astype(float).mean():.3f}", ""]
    m["bin"] = pd.cut(m.fair, [0, .05, .15, .3, .5, .7, .9, 1.0001], right=False)
    L += [m.groupby("bin", observed=True).agg(n=("y", "size"), modelo=("fair", "mean"), mercado=("px_yes", "mean"),
                                               freq=("y", "mean")).round(3).to_markdown(), ""]
lo, hi = h001.cluster_bootstrap(b, col="pnl", cluster="cl") if len(b) else (np.nan, np.nan)
ok = len(b) > 0 and b.pnl.mean() > 0 and lo > 0
L += ["## Veredicto G2", "",
      f"- Predicción (PnL > 0 con IC95% cluster > 0): {'CUMPLIDA' if ok else 'NO cumplida'}"]
open(os.path.join(ROOT, "reports", "h016_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
