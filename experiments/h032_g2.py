"""H032 G2 (solo entrenamiento, closedTime < 2026-04-12). Requiere experiments/h032_g1.py.

    PYTHONPATH=src python3 experiments/h032_g2.py --prefetch   (solo descarga trades, 3 hilos)
    PYTHONPATH=src python3 experiments/h032_g2.py              → reports/h032_g2.md

Protocolo pre-registrado (HYPOTHESES.md ### H032), 1 variante:
- t = inicio + 4 días; C = posts de la ventana con importedAt ≤ t.
- Resto ~ empírica de 8 ventanas contiguas de duración R = fin − t antes de t (importedAt ≤ t).
- P(tramo) = P(C + resto ∈ tramo); precio = peor compra taker real en (t, t + 30 min];
  señal prob − precio − comisión ≥ 0.05 (YES o NO). Cluster = evento (cuenta-semana).
"""
import hashlib, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h005, h014, h027, h032, trades
from pmq.universe import DATA

sys.path.insert(0, os.path.dirname(__file__))
from h032_g1 import posts  # noqa: E402  (caché de posts de XTracker)

D = os.path.join(DATA, "h032")
CACHE = os.path.join(DATA, "trades_h032")
W = h032.PRICE_WINDOW_S
rng = np.random.default_rng(0)
EPOCH = pd.Timestamp(0, tz="UTC")

ev = pd.read_parquet(os.path.join(D, "events.parquet"))
ev = ev[ev.usable].copy()
mk = pd.read_parquet(os.path.join(D, "markets.parquet"))
mk = mk[mk.event_id.isin(ev.index)].copy()
assert (mk.closed_time < h001.HOLDOUT_START).all()

# --- estado en t (solo información con importedAt ≤ t)
hist = {h: posts(h) for h in ev.handle.unique()}
ev["t"] = ev["t"].astype(int)
ev["C"] = [h032.current_count(*hist[h], int(s), int(t)) for h, s, t in zip(ev.handle, ev.start, ev.t)]
ev["samples"] = [h032.remaining_samples(*hist[h], int(t), int(R)) for h, t, R in zip(ev.handle, ev.t, ev.R)]
ev["month"] = pd.to_datetime(ev.start, unit="s").dt.strftime("%Y-%m")

e = mk.merge(ev[["handle", "t", "C", "samples", "month", "xt_count"]], left_on="event_id", right_index=True)
tt = pd.to_datetime(e.t, unit="s", utc=True)
e["open_at_t"] = (e.mk_start <= tt) & (e.closed_time > tt)
n_all = len(e)
cl = e[~e.open_at_t]
e = e[e.open_at_t].copy()
e["hi_int"] = [None if np.isinf(h) else int(h) for h in e.hi]
e["prob"] = [h032.bucket_prob(C, s, int(lo), hi) for C, s, lo, hi in zip(e.C, e.samples, e.lo, e.hi_int)]


def fetch_all(mm):
    with ThreadPoolExecutor(3) as ex:
        return list(ex.map(lambda r: trades.fetch(r[0], int(r[1]), int(r[1]) + W, CACHE),
                           zip(mm.condition_id, mm.t)))


if "--prefetch" in sys.argv:
    print("prefetch", len(e), flush=True)
    r = fetch_all(e)
    print("fallos", sum(x is None for x in r), flush=True)
    sys.exit()

e["rate"] = [h001.fee_rate(x) for x in e.fee_schedule]
res = fetch_all(e)
e["fail"] = [r is None for r in res]
e["px_yes"] = [h005.exec_price(r, 0, t, t + W) for r, t in zip(res, e.t)]
e["px_no"] = [h005.exec_price(r, 1, t, t + W) for r, t in zip(res, e.t)]
nn = lambda x: None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)
d = [h032.decide(p, nn(py), nn(pn), rt) for p, py, pn, rt in zip(e.prob, e.px_yes, e.px_no, e.rate)]
e["side"], e["px"], e["edge"] = zip(*d)
b = e[e.side.notna()].copy()
b["pnl"] = [h005.pnl(s, p, r, y) for s, p, r, y in zip(b.side, b.px, b.rate, b.y)]
spread = (b.px_yes.astype(float) + b.px_no.astype(float) - 1) / 2
b["slip2"] = np.where(spread.notna(), np.maximum(spread.fillna(0), 0.01), 0.01)
b["pnl2"] = [h014.pnl(s, p, r, y, 2.0, sl) for s, p, r, y, sl in zip(b.side, b.px, b.rate, b.y, b.slip2)]
b["cap"] = b.px + [h014.fee(p, r) for p, r in zip(b.px, b.rate)]
b["cap2"] = [min(p + s, 0.999) + 2 * h014.fee(min(p + s, 0.999), r) for p, s, r in zip(b.px, b.slip2, b.rate)]
b["days"] = ((b.closed_time - pd.to_datetime(b.t, unit="s", utc=True)).dt.total_seconds() / 86400).clip(lower=1 / 24)
b["t_close"] = (b.closed_time - EPOCH) // pd.Timedelta(seconds=1)
b["acct_month"] = b.handle + "_" + b.month


def ci(df, col, cluster="event_id"):
    return h001.cluster_bootstrap(df, col=col, cluster=cluster) if len(df) else (np.nan, np.nan)


def ci_port(df, col="pnl", cap="cap", n=2000):
    dd = df.assign(cd=df[cap] * df.days)
    g = dd.groupby("event_id").agg(a=(col, "sum"), c=("cd", "sum"))
    a, c = g.a.values, g.c.values
    idx = rng.integers(0, len(g), (n, len(g)))
    return np.percentile(a[idx].sum(1) / c[idx].sum(1) * 365, [2.5, 97.5])


nb = len(b)
lo, hi = ci(b, "pnl")
lom, him = ci(b, "pnl", "acct_month")
lo2, hi2 = ci(b, "pnl2")
top = b.groupby("event_id").pnl.sum().sort_values(ascending=False).index[:5]
b5 = b[~b.event_id.isin(top)]
lo5, hi5 = ci(b5, "pnl")
port = h027.portfolio_return(b.pnl, b.cap, b.days) if nb else np.nan
plo, phi = ci_port(b) if nb else (np.nan, np.nan)
port2 = h027.portfolio_return(b.pnl2, b.cap2, b.days) if nb else np.nan
bank, peak = h027.bankroll_return(b.pnl, b.cap, b.t, b.t_close) if nb else (np.nan, np.nan)

# --- Brier / log loss modelo vs precio ejecutable YES
q = e[e.px_yes.notna()].copy()
q["px_yes"] = q.px_yes.astype(float)
q["d_brier"] = (q.prob - q.y) ** 2 - (q.px_yes - q.y) ** 2
eps = 1e-3
ll = lambda p, y: -(y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps)))
q["d_ll"] = ll(q.prob, q.y) - ll(q.px_yes, q.y)
blo, bhi = ci(q, "d_brier")
llo, lhi = ci(q, "d_ll")
# posición del resultado final en la distribución del modelo (calibración de la predicción del total)
ev["pit"] = [float(np.mean(C + s < x) + 0.5 * np.mean(C + s == x)) for C, s, x in zip(ev.C, ev.samples, ev.xt_count)]
ev["in_range"] = [(C + s.min()) <= x <= (C + s.max()) for C, s, x in zip(ev.C, ev.samples, ev.xt_count)]

commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
f = lambda x: "nan" if x != x else f"{x*100:+.2f}"
L = ["# H032 G2 — recuento de posts semanales con XTracker (solo entrenamiento)", "",
     f"- commit {commit}; `PYTHONPATH=src python3 experiments/h032_g1.py && PYTHONPATH=src python3 experiments/h032_g2.py`; "
     f"events.parquet {sha(os.path.join(D, 'events.parquet'))}, markets.parquet {sha(os.path.join(D, 'markets.parquet'))}",
     "- 1 variante (t = inicio + 4 d; importedAt ≤ t; 8 ventanas contiguas de duración R; θ = 0.05; precio = peor compra "
     "taker en (t, t+30 min]).",
     f"- eventos utilizables (G1): {len(ev)} ({', '.join(f'{h} {n}' for h, n in ev.handle.value_counts().items())}); "
     f"mercados {n_all:,}; abiertos en t: {len(e):,}; ya cerrados en t (tramos muertos, resueltos NO antes de t): "
     f"{len(cl):,} (YES entre ellos: {int((cl.y == 1).sum())})",
     f"- mercados con compra taker YES en (t, t+30 min]: {int(e.px_yes.notna().sum()):,}; NO: {int(e.px_no.notna().sum()):,}; "
     f"fallos de descarga: {int(e.fail.sum())}",
     "", "## Resultado", "",
     f"- apuestas: {nb:,} en {b.event_id.nunique() if nb else 0} eventos (YES {int((b.side == 'YES').sum())}, "
     f"NO {int((b.side == 'NO').sum())}); edge esperado medio {f(b.edge.mean())} c; precio medio {b.px.mean():.3f}",
     f"- **PnL medio por acción {f(b.pnl.mean())} c (IC95% cluster evento {f(lo)} … {f(hi)})**; "
     f"IC95% cluster cuenta-mes {f(lom)} … {f(him)}; PnL total {b.pnl.sum():+.2f} USD por 1 acción/apuesta; "
     f"aciertos {(b.pnl > 0).mean():.1%}",
     f"- costes ×2 (comisión ×2 + deslizamiento extra = max(0.01, (pYES+pNO−1)/2)): {f(b.pnl2.mean())} c "
     f"(IC95% {f(lo2)} … {f(hi2)})",
     f"- sin los 5 mejores eventos: n={len(b5):,}, {f(b5.pnl.mean())} c (IC95% {f(lo5)} … {f(hi5)})",
     "- por lado: " + "; ".join(f"{s}: n={len(g)}, {f(g.pnl.mean())} c, aciertos {(g.pnl > 0).mean():.0%}"
                                for s, g in b.groupby("side")),
     "- por cuenta: " + "; ".join(f"{h}: n={len(g)} en {g.event_id.nunique()} ev, {f(g.pnl.mean())} c"
                                  for h, g in b.groupby("handle")),
     "- por prob. del modelo: " + "; ".join(
         f"{k}: n={len(g)}, {f(g.pnl.mean())} c" for k, g in b.groupby(pd.cut(b.prob, [-0.001, 0.0, 0.5, 0.999, 1.0]), observed=True)),
     f"- tasa de comisión media {b.rate.mean():.3f}; días medios de capital bloqueado {b.days.mean():.2f}",
     f"- **rentabilidad de cartera Σpnl/Σ(capital·días)·365 = {port:+.1%} (IC95% cluster {plo:+.1%} … {phi:+.1%})**; "
     f"costes ×2: {port2:+.1%}; con capital ocioso (banca = máx. capital simultáneo {peak:.2f} USD/acción): {bank:+.1%} anual",
     "", "## Probabilidad: modelo vs precio ejecutable", "",
     f"- mercados con precio YES ejecutable: {len(q):,} en {q.event_id.nunique()} eventos",
     f"- Brier modelo {((q.prob - q.y) ** 2).mean():.4f} vs precio {((q.px_yes - q.y) ** 2).mean():.4f}; diferencia "
     f"{q.d_brier.mean():+.4f} (IC95% cluster {blo:+.4f} … {bhi:+.4f})",
     f"- log loss (recorte 1e-3) modelo {ll(q.prob, q.y).mean():.4f} vs precio {ll(q.px_yes, q.y).mean():.4f}; diferencia "
     f"{q.d_ll.mean():+.4f} (IC95% {llo:+.4f} … {lhi:+.4f})",
     f"- total final dentro del rango [C + min, C + max] de las 8 muestras: {ev.in_range.mean():.0%} de los eventos "
     f"(esperado con 8 muestras intercambiables: 7/9 = 78%); PIT medio {ev.pit.mean():.2f} (0.5 = sin sesgo)",
     f"- suma de prob. del modelo sobre los tramos abiertos por evento: media {e.groupby('event_id').prob.sum().mean():.3f}",
     "", "## Por evento", "", "| cuenta | ventana | C en t | resto (8 muestras) | final | apuestas | PnL |", "|---|---|---|---|---|---|---|"]
for eid, r in ev.sort_values("start").iterrows():
    g = b[b.event_id == eid]
    L.append(f"| {r.handle} | {pd.to_datetime(r.start, unit='s'):%Y-%m-%d} | {r.C} | {','.join(map(str, r.samples))} | "
             f"{int(r.xt_count)} | {len(g)} | {g.pnl.sum():+.2f} |")
nev = b.event_id.nunique() if nb else 0
pred1 = lo > 0
pred2 = len(q) and q.d_brier.mean() < 0
L += ["", "## Predicción falsable", "",
      f"- PnL > 0 con IC95% cluster > 0: **{'CUMPLIDA' if pred1 else 'NO cumplida'}**",
      f"- Brier modelo < Brier precio: **{'CUMPLIDA' if pred2 else 'NO cumplida'}** "
      f"({'mejora significativa' if bhi < 0 else ('el modelo es significativamente PEOR' if blo > 0 else 'diferencia no significativa')} al 95%)",
      f"- ≥ 150 eventos: **NO** ({len(ev)} utilizables, {nev} con apuesta). G4 es INVIABLE con los datos de entrenamiento: "
      "XTracker solo tiene historial desde nov-2025 (Elon) o ene–mar 2026 (resto) y el holdout empieza el 2026-04-12. "
      "Según el protocolo, la hipótesis pasa a forward (paper trading) si se quiere seguir.",
      "", "## Sustituciones", "",
      "1. 'Últimas 8 ventanas no solapadas' = 8 bloques contiguos de duración R terminando en t (decidido antes de ver "
      "resultados; la alternativa de misma fase semanal exigía 56 días de historial y dejaba casi sin eventos).",
      "2. Recuento C y muestras: solo posts con importedAt ≤ t (cargas retroactivas posteriores no cuentan).",
      "3. Días de capital = closedTime del mercado − t (el pago llega al resolver). Mercados ya cerrados en t se excluyen.",
      "4. Cuenta realDonaldTrump excluida en G1 (concordancia 88% < 97%); CZ, Khamenei, NYC Mayor y Zelenskyy sin "
      "historial suficiente antes del holdout; series de 48 h y mensuales fuera del diseño semanal.",
      "5. Ventanas de Elon solapadas (mar–mar y vie–vie): además del cluster por evento se da el IC por cuenta-mes."]
open(os.path.join(ROOT, "reports", "h032_g2.md"), "w").write("\n".join(L) + "\n")
b.drop(columns=["samples"]).to_parquet(os.path.join(D, "g2_bets.parquet"))
print("\n".join(L))
