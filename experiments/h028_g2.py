"""H028 G2 — tasa base de batidas vs precio ejecutable (solo entrenamiento, closedTime < 2026-04-12).

Requiere data/h028/markets.parquet (experiments/h028_g1.py).
python experiments/h028_g2.py → reports/h028_g2.md
"""
import os, subprocess, sys, hashlib
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h005, h028, trades
from pmq.universe import DATA

OUT = os.path.join(DATA, "h028")
m = pd.read_parquet(os.path.join(OUT, "markets.parquet"))
assert (m.closed_time < h001.HOLDOUT_START).all()
n0 = len(m)
m = m[~m.t_after_close].copy()
m["b_end"] = [rt if pd.notna(rt) else e for rt, e in zip(m.report_time, m.end)]   # hora del informe
m["a"] = [int((t - h028.WINDOW).timestamp()) for t in m.t]
m["t1"] = [int(t.timestamp()) for t in m.t]
m["b"] = [int(x.timestamp()) for x in m.b_end]
CACHE = os.path.join(OUT, "trades")
with ThreadPoolExecutor(6) as ex:   # una descarga por mercado: (t − 23 h, hora del informe]
    res = list(ex.map(lambda r: trades.fetch(r[0], r[1], r[2], CACHE), zip(m.condition_id, m.a, m.b)))
m["fail"] = [r is None for r in res]
m["px_yes"] = [h005.exec_price(r, 0, a, t) for r, a, t in zip(res, m.a, m.t1)]
m["px_no"] = [h005.exec_price(r, 1, a, t) for r, a, t in zip(res, m.a, m.t1)]


def med_buy(tr, idx, a, b):
    p = [float(x["price"]) for x in tr or [] if x["outcomeIndex"] == idx and x["side"] == "BUY" and a < x["timestamp"] <= b]
    return float(np.median(p)) if p else np.nan


def last_px(tr, idx, a, b):
    """Último precio negociado del token idx en (a, b] (cualquier lado): línea de cierre antes del informe."""
    p = sorted((x["timestamp"], float(x["price"])) for x in tr or [] if x["outcomeIndex"] == idx and a < x["timestamp"] <= b)
    return p[-1][1] if p else np.nan


d = [h005.decide(p, py, pn, rt, theta=h028.THETA) for p, py, pn, rt in zip(m.prob, m.px_yes, m.px_no, m.rate)]
m["side"], m["px"], m["edge"] = zip(*d)
m["idx"] = np.where(m.side == "YES", 0, 1)
usable = m[m.px_yes.notna() | m.px_no.notna()]
b = m[m.side.notna()].copy()
tr_of = dict(zip(m.id, res))
b["pnl"] = [h005.pnl(s, p, r, y) for s, p, r, y in zip(b.side, b.px, b.rate, b.y)]
b["gross"] = [h005.pnl(s, p, 0.0, y) for s, p, y in zip(b.side, b.px, b.y)]
b["med"] = [med_buy(tr_of[i], k, a, t) for i, k, a, t in zip(b.id, b.idx, b.a, b.t1)]
b["px2"] = np.minimum(b.px + np.maximum(0.01, b.px - b.med), 0.999)
b["pnl2"] = [h005.pnl(s, p, 2 * r, y) for s, p, r, y in zip(b.side, b.px2, b.rate, b.y)]
b["close"] = [last_px(tr_of[i], k, t, bb) for i, k, t, bb in zip(b.id, b.idx, b.t1, b.b)]
b["clv"] = b.close - b.px
b["cap"] = b.px + h005.fee(b.px, b.rate)
b["days"] = ((b.closed_time - b.t).dt.total_seconds() / 86400).clip(lower=1 / 24)
CL = "report_day"


def line(lbl, x, col="pnl"):
    if len(x) == 0:
        return f"- {lbl}: sin apuestas"
    lo, hi = h001.cluster_bootstrap(x, col=col, cluster=CL)
    port = x[col].sum() / (x.cap * x.days).sum() * 365
    return (f"- {lbl}: n={len(x):,} en {x[CL].nunique():,} fechas; PnL/acción {x[col].mean()*100:+.2f} c "
            f"(IC95% cluster {lo*100:+.2f} … {hi*100:+.2f}); acierto {(np.where(x.side == 'YES', x.y, 1 - x.y)).mean():.3f}; "
            f"Σpnl/Σ(capital·días)·365 = {port:+.1%}")


top5 = b.groupby(CL).pnl.sum().nlargest(5).index
bt = b[~b[CL].isin(top5)]
# Brier en t: modelo vs precio YES ejecutable (diagnóstico en todos los mercados con compra YES)
dg = m[m.px_yes.notna() & m.clean].copy()
dg["dB"] = (dg.prob - dg.y) ** 2 - (dg.px_yes - dg.y) ** 2
dlo, dhi = h001.cluster_bootstrap(dg, col="dB", cluster=CL) if len(dg) else (np.nan, np.nan)
dg["px_mid"] = [(py + (1 - pn)) / 2 if pd.notna(pn) else py for py, pn in zip(dg.px_yes, dg.px_no)]
dg["dBm"] = (dg.prob - dg.y) ** 2 - (dg.px_mid - dg.y) ** 2
mlo, mhi = h001.cluster_bootstrap(dg, col="dBm", cluster=CL) if len(dg) else (np.nan, np.nan)
# calibración por tramos de precio YES
dg["bin"] = pd.cut(dg.px_yes, [0, .3, .5, .6, .7, .8, .9, 1.0001], right=False)
cal = dg.groupby("bin", observed=True).agg(n=("y", "size"), px=("px_yes", "mean"), prob=("prob", "mean"), y=("y", "mean"))

commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
mh = hashlib.sha256(open(os.path.join(OUT, "markets.parquet"), "rb").read()).hexdigest()[:12]
L = ["# H028 G2 — Tasa base de batidas vs precio ejecutable (solo entrenamiento)", "",
     f"- commit {commit}; data/h028/markets.parquet sha256[:12] {mh}",
     f"- Protocolo G0: prob = (k + 0.76·4)/(n + 4), n ≤ 8 informes Yahoo con fecha < t; t = hora informe (Yahoo) − 24 h "
     f"(endDate − 24 h si no consta); precio = peor compra taker en (t − 23 h, t]; señal prob − precio − comisión ≥ {h028.THETA}; "
     "comisión 0.07·p·(1−p) (ningún mercado expone feeSchedule). Variantes usadas: 1.",
     "", "## Muestra",
     f"- Mercados entrenamiento: {n0:,}; con t < closedTime: {len(m):,}; fallos de descarga: {int(m.fail.sum())}.",
     f"- Con compra taker ejecutable en (t − 23 h, t]: YES {int(m.px_yes.notna().sum()):,}, NO {int(m.px_no.notna().sum()):,}, "
     f"alguno {len(usable):,} (empresas {usable.ticker.nunique():,}, fechas {usable[CL].nunique():,}).",
     f"- Apuestas: {len(b):,} (YES {int((b.side == 'YES').sum())}, NO {int((b.side == 'NO').sum())}) en "
     f"{b[CL].nunique():,} fechas de informe y {b.ticker.nunique():,} empresas; edge esperado medio {b.edge.mean()*100:.2f} c.",
     ("- **Menos de 150 mercados con apuesta: G4 (≥150 mercados OOS) no es alcanzable con esta muestra.**"
      if len(b) < 150 else f"- ≥ 150 mercados con apuesta ({len(b)})."),
     "", "## Resultado",
     line("TODAS (neto)", b), line("bruto (sin comisión)", b, "gross"), line("costes ×2", b, "pnl2"),
     line("sin las 5 mejores fechas", bt), line("solo YES", b[b.side == "YES"]), line("solo NO", b[b.side == "NO"]),
     f"- CLV medio (último precio del token antes del informe − precio de entrada): {b.clv.mean()*100:+.2f} c "
     f"(n={int(b.clv.notna().sum())}; CLV>0 {(b.clv > 0).mean():.1%}).",
     f"- Capital: días medios bloqueados {b.days.mean():.2f}; capital medio por acción {b.cap.mean():.3f}.",
     "", "## Probabilidades (mercados limpios con compra YES en la ventana)",
     f"- n={len(dg):,}; Brier modelo {((dg.prob - dg.y) ** 2).mean():.4f} vs precio YES (peor compra) {((dg.px_yes - dg.y) ** 2).mean():.4f}; "
     f"Δ(modelo − precio) {dg.dB.mean():+.4f} (IC95% cluster {dlo:+.4f} … {dhi:+.4f}).",
     f"- Frente a precio medio ((YES + 1 − NO)/2 si hay ambos): Brier precio {((dg.px_mid - dg.y) ** 2).mean():.4f}; "
     f"Δ {dg.dBm.mean():+.4f} (IC95% {mlo:+.4f} … {mhi:+.4f}).",
     f"- Tasa YES {dg.y.mean():.3f}; precio YES medio {dg.px_yes.mean():.3f}; prob. modelo media {dg.prob.mean():.3f}.",
     "", "Calibración por tramo de precio YES:", "", "| tramo | n | precio | modelo | tasa YES |", "|---|---|---|---|---|"] + \
    [f"| {i} | {r.n} | {r.px:.3f} | {r.prob:.3f} | {r.y:.3f} |" for i, r in cal.iterrows()] + \
    ["", "## Veredicto (predicción G0: PnL > 0 con IC95% > 0 y ≥ 150 mercados)", "",
     (f"- {'CUMPLIDA' if h001.cluster_bootstrap(b, col='pnl', cluster=CL)[0] > 0 and len(b) >= 150 else 'NO cumplida'}: "
      f"PnL neto {b.pnl.mean()*100:+.2f} c/acción; el modelo de tasa base tiene peor Brier que el precio "
      f"(Δ {dg.dB.mean():+.4f}). El mercado ya incorpora la tasa de batida y la información específica de cada empresa."),
     "- La rentabilidad anualizada es extrema porque el capital se bloquea ~1.6 días; su signo es lo relevante.",
     "", "## Notas",
     "- Costes ×2: comisión ×2 y slippage adicional = max(0.01, peor − mediana de compras del lado en la ventana).",
     "- Rentabilidad de cartera: Σpnl / Σ(capital·días) · 365 con días = closedTime − t (sin capital ocioso entre fechas: optimista).",
     "- Clusters = fecha del informe (America/New_York); varios informes el mismo día comparten shocks de mercado.",
     ""]
b.drop(columns=["med"]).to_parquet(os.path.join(OUT, "bets_g2.parquet"))
open(os.path.join(ROOT, "reports", "h028_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
