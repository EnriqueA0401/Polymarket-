"""H014 G2 (solo entrenamiento, closedTime < 2026-04-12). Requiere haber corrido experiments/h014_g1.py.

    PYTHONPATH=src python3 experiments/h014_g2.py              → reports/h014_g2.md
    PYTHONPATH=src python3 experiments/h014_g2.py --prefetch   (solo descarga trades)

Protocolo pre-registrado (HYPOTHESES.md ### H014): modelo de error normal por ciudad estimado en la
PRIMERA mitad temporal del entrenamiento (eventos con fecha objetivo < mediana), evaluación en la
SEGUNDA mitad. t = 12:00 UTC del día anterior; precio = peor compra taker real en (t−1h, t];
señal prob − precio − comisión ≥ 0.05 (YES o NO). 1 variante.
"""
import hashlib, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h005, h014, trades
from pmq.universe import DATA

D = os.path.join(DATA, "h014")
CACHE = os.path.join(DATA, "trades_h014")

m = pd.read_parquet(os.path.join(D, "markets.parquet"))
evt = m.groupby("event_id").target.first().sort_values()
SPLIT = evt.iloc[len(evt) // 2]                     # mediana de fechas objetivo de los eventos de entrenamiento
m["half"] = np.where(m.target < SPLIT, 1, 2)
n1 = m[m.half == 1].groupby("city").event_id.nunique()


def prefetch(mm):
    mm = mm.assign(t0=mm.t_dec - 3600)
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda r: trades.fetch(r[0], r[1], r[2], CACHE), zip(mm.condition_id, mm.t0, mm.t_dec)))
    return res


if "--prefetch" in sys.argv:
    mm = m[(m.half == 2) & m.city.isin(n1[n1 >= h014.MIN_FIT].index)]
    print("prefetch", len(mm), flush=True)
    r = prefetch(mm)
    print("fallos", sum(x is None for x in r))
    sys.exit()

fc = pd.read_parquet(os.path.join(D, "forecasts.parquet"))[["event_id", "fc"]]
m = m.merge(fc, on="event_id", how="left")

# --- ajuste del modelo de error (primera mitad): eventos limpios con exactamente un YES
ev_ok = m.groupby("event_id").agg(nyes=("y", lambda s: (s == 1).sum()), allclean=("clean", "all"))
ev_ok = ev_ok[(ev_ok.nyes == 1) & ev_ok.allclean].index
w = m[(m.half == 1) & m.event_id.isin(ev_ok) & (m.y == 1) & m.fc.notna()]
params = {}
for c, g in w.groupby("city"):
    if len(g) >= h014.MIN_FIT:
        params[c] = h014.fit_error(g.a_c - g.fc, g.b_c - g.fc) + (len(g),)

# --- evaluación (segunda mitad)
e = m[(m.half == 2) & m.city.isin(list(params)) & m.fc.notna()].copy()
e["prob"] = [h014.bucket_prob(f, params[c][0], params[c][1], a, b) for f, c, a, b in zip(e.fc, e.city, e.a_c, e.b_c)]
e["rate"] = [h001.fee_rate(x) for x in e.fee_schedule]
res = prefetch(e)
e["fail"] = [r is None for r in res]
e["px_yes"] = [h005.exec_price(r, 0, t - 3600, t) for r, t in zip(res, e.t_dec)]
e["px_no"] = [h005.exec_price(r, 1, t - 3600, t) for r, t in zip(res, e.t_dec)]
d = [h014.decide(p, py, pn, rt) for p, py, pn, rt in zip(e.prob, e.px_yes, e.px_no, e.rate)]
e["side"], e["px"], e["edge"] = zip(*d)
b = e[e.side.notna()].copy()
b["pnl"] = [h014.pnl(s, p, r, y) for s, p, r, y in zip(b.side, b.px, b.rate, b.y)]
spread = (b.px_yes + b.px_no - 1) / 2
b["slip2"] = np.where(spread.notna(), np.maximum(spread.fillna(0), 0.01), 0.01)
b["pnl2"] = [h014.pnl(s, p, r, y, 2.0, sl) for s, p, r, y, sl in zip(b.side, b.px, b.rate, b.y, b.slip2)]
b["ret"] = b.pnl / (b.px + [h014.fee(p, r) for p, r in zip(b.px, b.rate)])


def ci(df, col):
    return h001.cluster_bootstrap(df, col=col, cluster="event_id") if len(df) else (np.nan, np.nan)


lo, hi = ci(b, "pnl")
lo2, hi2 = ci(b, "pnl2")
top = b.groupby("event_id").pnl.sum().sort_values(ascending=False).index[:5]
b5 = b[~b.event_id.isin(top)]
lo5, hi5 = ci(b5, "pnl")

# --- Brier / log loss del modelo vs precio ejecutable YES (mercados limpios con trade YES en la ventana)
q = e[e.px_yes.notna() & e.clean].copy()
q["d_brier"] = (q.prob - q.y) ** 2 - (q.px_yes - q.y) ** 2
eps = 1e-3
ll = lambda p, y: -(y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps)))
q["d_ll"] = ll(q.prob, q.y) - ll(q.px_yes, q.y)
blo, bhi = ci(q, "d_brier")
llo, lhi = ci(q, "d_ll")
# Brier del modelo en todos los mercados evaluados limpios (sin requerir precio)
ea = e[e.clean]

commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
L = ["# H014 G2 — temperatura máxima vs pronóstico Open-Meteo (solo entrenamiento)", "",
     f"- commit {commit}; `PYTHONPATH=src python3 experiments/h014_g2.py`; markets.parquet {sha(os.path.join(D, 'markets.parquet'))}, "
     f"forecasts.parquet {sha(os.path.join(D, 'forecasts.parquet'))}",
     f"- división temporal: fecha objetivo < {SPLIT} → ajuste (mitad 1, {int((evt < SPLIT).sum())} eventos); ≥ {SPLIT} → evaluación "
     f"(mitad 2, {int((evt >= SPLIT).sum())} eventos). Variantes: 1 (θ=0.05, t=12:00 UTC D−1, ventana 1 h).",
     f"- ciudades con modelo (≥ {h014.MIN_FIT} eventos con pronóstico en mitad 1): {len(params)}; "
     f"mercados de mitad 2 evaluables (ciudad con modelo y pronóstico): {len(e):,} en {e.event_id.nunique():,} eventos; "
     f"fallos descarga trades: {int(e.fail.sum())}",
     f"- mercados con compra taker YES en (t−1h, t]: {int(e.px_yes.notna().sum()):,}; NO: {int(e.px_no.notna().sum()):,}",
     "", "## Modelo de error (mitad 1; observado − pronóstico, °C, MLE censurado)", "",
     "| ciudad | n eventos | media | sd |", "|---|---|---|---|"]
for c, (mu, sd, n) in sorted(params.items()):
    L.append(f"| {c} | {n} | {mu:+.2f} | {sd:.2f} |")
L += ["", "## Resultado (mitad 2)", "",
      f"- apuestas: {len(b):,} en {b.event_id.nunique():,} eventos (ciudad-fecha) "
      f"(YES {int((b.side == 'YES').sum())}, NO {int((b.side == 'NO').sum())}); edge esperado medio {b.edge.mean()*100:.2f} c",
      f"- **PnL medio por acción {b.pnl.mean()*100:+.3f} c (IC95% cluster evento {lo*100:+.3f} … {hi*100:+.3f})**; "
      f"retorno medio por apuesta {b.ret.mean():+.2%}; PnL total {b.pnl.sum():+.2f} USD por 1 acción/apuesta",
      f"- costes ×2 (comisión ×2 + deslizamiento extra = max(0.01, (pYES+pNO−1)/2)): {b.pnl2.mean()*100:+.3f} c "
      f"(IC95% {lo2*100:+.3f} … {hi2*100:+.3f})",
      f"- sin los 5 mejores eventos: n={len(b5):,}, {b5.pnl.mean()*100:+.3f} c (IC95% {lo5*100:+.3f} … {hi5*100:+.3f})",
      f"- por lado: " + "; ".join(f"{s}: n={len(g)}, {g.pnl.mean()*100:+.2f} c" for s, g in b.groupby("side")),
      f"- tasa de comisión media aplicada {b.rate.mean():.3f} (h001.fee_rate; 0.07 pesimista si el mercado no expone feeSchedule)",
      "", "## Probabilidad: modelo vs precio ejecutable", "",
      f"- mercados limpios con precio YES ejecutable: {len(q):,} en {q.event_id.nunique():,} eventos",
      f"- Brier modelo {((q.prob - q.y) ** 2).mean():.4f} vs precio {((q.px_yes - q.y) ** 2).mean():.4f}; "
      f"diferencia {q.d_brier.mean():+.4f} (IC95% cluster {blo:+.4f} … {bhi:+.4f})",
      f"- log loss modelo {ll(q.prob, q.y).mean():.4f} vs precio {ll(q.px_yes, q.y).mean():.4f}; diferencia {q.d_ll.mean():+.4f} "
      f"(IC95% {llo:+.4f} … {lhi:+.4f})",
      f"- Brier del modelo en todos los mercados limpios evaluables (n={len(ea):,}): {((ea.prob - ea.y) ** 2).mean():.4f}; "
      f"suma de prob por evento: media {e.groupby('event_id').prob.sum().mean():.3f}",
      "", "## Por ciudad", "", "| ciudad | apuestas | eventos | PnL medio c |", "|---|---|---|---|"]
for c, g in b.groupby("city"):
    L.append(f"| {c} | {len(g)} | {g.event_id.nunique()} | {g.pnl.mean()*100:+.2f} |")
pred = (lo > 0)
L += ["", "## Predicción falsable", "",
      f"- PnL > 0 con IC95% cluster (ciudad-fecha) > 0: **{'CUMPLIDA' if pred else 'NO cumplida'}**"]
open(os.path.join(ROOT, "reports", "h014_g2.md"), "w").write("\n".join(L) + "\n")
b.drop(columns=[c for c in b.columns if c in ("start", "end")]).to_parquet(os.path.join(D, "g2_bets.parquet"))
print("\n".join(L))
