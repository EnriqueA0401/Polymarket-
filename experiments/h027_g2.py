"""H027 G2 (solo entrenamiento, closedTime < 2026-04-12). Requiere experiments/h027_g1.py.

    PYTHONPATH=src python3 experiments/h027_g2.py --prefetch   (solo descarga trades, 3 hilos)
    PYTHONPATH=src python3 experiments/h027_g2.py              → reports/h027_g2.md

Protocolo pre-registrado (HYPOTHESES.md ### H027): distribución empírica por ciudad (y unidad) de
R = máximo final METAR − máximo acumulado a las 15:00 locales (obs ≤ t − 15 min), estimada en la PRIMERA
mitad temporal del entrenamiento (misma división que H014: fecha objetivo < mediana de eventos), evaluada
en la SEGUNDA. Precio = peor compra taker real en (t, t+10 min]; señal prob − precio − comisión ≥ 0.05
(YES o NO). Clusters = evento (ciudad-fecha). 1 variante.
"""
import hashlib, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h004, h005, h014, h027, trades
from pmq.universe import DATA

D = os.path.join(DATA, "h027")
CACHE = os.path.join(DATA, "trades_h027")
rng = np.random.default_rng(0)

m = pd.read_parquet(os.path.join(DATA, "h014", "markets.parquet"))
assert (m.closed_time < h001.HOLDOUT_START).all()
evt = m.groupby("event_id").target.first().sort_values()
SPLIT = evt.iloc[len(evt) // 2]                      # idéntica a H014
ev = pd.read_parquet(os.path.join(D, "events.parquet"))
ev["half"] = np.where(ev.target < SPLIT, 1, 2)

# --- ajuste (mitad 1): R = Xmax − M por (ciudad, unidad), solo ciudades que pasan G1
f = ev[(ev.half == 1) & ev.city_ok & ev.M.notna() & ev.Xmax.notna()]
dists = {}
for (c, u), g in f.groupby(["city", "unit"]):
    if len(g) >= h027.MIN_FIT:
        dists[(c, u)] = (h027.fit_rise((g.Xmax - g.M).astype(int)), len(g))

# --- evaluación (mitad 2)
e = m.merge(ev[["event_id", "half", "city_ok", "M", "Xmax", "t_dec"]].rename(columns={"t_dec": "t"}), on="event_id")
e = e[(e.half == 2) & e.city_ok & e.M.notna()]
e = e[[(c, u) in dists for c, u in zip(e.city, e.unit)]].copy()
n_eval_all = len(e)
tt = pd.to_datetime(e.t, unit="s", utc=True)
e["open_at_t"] = (e.start <= tt) & (e.closed_time > tt)
cl = e[e.closed_time <= tt]
cl_hi = np.array([h027.bucket_ints(k, a, bb)[1] for k, a, bb in zip(cl.kind, cl.lo, cl.hi)], dtype=float)
cl_y0, cl_dead = float((cl.y == 0).mean()), float((cl.M.values > cl_hi).mean())
e = e[e.open_at_t].copy()


def fetch_all(mm):
    with ThreadPoolExecutor(3) as ex:
        return list(ex.map(lambda r: trades.fetch(r[0], int(r[1]), int(r[1]) + h027.WINDOW_S, CACHE),
                           zip(mm.condition_id, mm.t)))


if "--prefetch" in sys.argv:
    print("prefetch", len(e), flush=True)
    r = fetch_all(e)
    print("fallos", sum(x is None for x in r), flush=True)
    sys.exit()

ia_ib = [h027.bucket_ints(k, a, b) for k, a, b in zip(e.kind, e.lo, e.hi)]
e["ia"], e["ib"] = zip(*ia_ib)
e["prob"] = [h027.bucket_prob(int(M), dists[(c, u)][0], a, b) for M, c, u, a, b in zip(e.M, e.city, e.unit, e.ia, e.ib)]
e["rate"] = [h001.fee_rate(x) for x in e.fee_schedule]
res = fetch_all(e)
e["fail"] = [r is None for r in res]
W = h027.WINDOW_S
e["px_yes"] = [h005.exec_price(r, 0, t, t + W) for r, t in zip(res, e.t)]
e["px_no"] = [h005.exec_price(r, 1, t, t + W) for r, t in zip(res, e.t)]
d = [h027.decide(p, py, pn, rt) for p, py, pn, rt in zip(e.prob, e.px_yes, e.px_no, e.rate)]
e["side"], e["px"], e["edge"] = zip(*d)
b = e[e.side.notna()].copy()
b["idx"] = np.where(b.side == "YES", 0, 1)
b["pnl"] = [h004.pnl(i, p, r, y) for i, p, r, y in zip(b.idx, b.px, b.rate, b.y)]
spread = (b.px_yes + b.px_no - 1) / 2
b["slip2"] = np.where(spread.notna(), np.maximum(spread.fillna(0), 0.01), 0.01)
b["pnl2"] = [h014.pnl(s, p, r, y, 2.0, sl) for s, p, r, y, sl in zip(b.side, b.px, b.rate, b.y, b.slip2)]
b["cap"] = b.px + [h014.fee(p, r) for p, r in zip(b.px, b.rate)]
b["cap2"] = [min(p + s, 0.999) + 2 * h014.fee(min(p + s, 0.999), r) for p, s, r in zip(b.px, b.slip2, b.rate)]
b["days"] = ((b.closed_time - pd.to_datetime(b.t, unit="s", utc=True)).dt.total_seconds() / 86400).clip(lower=1 / 24)
b["t_close"] = (b.closed_time - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(seconds=1)


def ci(df, col):
    return h001.cluster_bootstrap(df, col=col, cluster="event_id") if len(df) else (np.nan, np.nan)


def ci_port(df, col="pnl", cap="cap", n=2000):
    d = df.assign(cd=df[cap] * df.days)
    g = d.groupby("event_id").agg(a=(col, "sum"), c=("cd", "sum"))
    a, c = g.a.values, g.c.values
    idx = rng.integers(0, len(g), (n, len(g)))
    return np.percentile(a[idx].sum(1) / c[idx].sum(1) * 365, [2.5, 97.5])


lo, hi = ci(b, "pnl")
lo2, hi2 = ci(b, "pnl2")
top = b.groupby("event_id").pnl.sum().sort_values(ascending=False).index[:5]
b5 = b[~b.event_id.isin(top)]
lo5, hi5 = ci(b5, "pnl")
port = h027.portfolio_return(b.pnl, b.cap, b.days) if len(b) else np.nan
plo, phi = ci_port(b) if len(b) else (np.nan, np.nan)
port2 = h027.portfolio_return(b.pnl2, b.cap2, b.days) if len(b) else np.nan
bank, peak = h027.bankroll_return(b.pnl, b.cap, b.t, b.t_close) if len(b) else (np.nan, np.nan)

# --- Brier / log loss modelo vs precio ejecutable YES
q = e[e.px_yes.notna() & e.clean].copy()
q["d_brier"] = (q.prob - q.y) ** 2 - (q.px_yes - q.y) ** 2
eps = 1e-3
ll = lambda p, y: -(y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps)))
q["d_ll"] = ll(q.prob, q.y) - ll(q.px_yes, q.y)
blo, bhi = ci(q, "d_brier")
llo, lhi = ci(q, "d_ll")
ea = e[e.clean]
# calibración del modelo en todos los mercados evaluados (sin requerir precio)
ea_bins = pd.cut(ea.prob, [-0.001, 0.0, 0.05, 0.2, 0.5, 0.8, 0.95, 0.999, 1.0])

commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
L = ["# H027 G2 — nowcast METAR del máximo del mismo día (solo entrenamiento)", "",
     f"- commit {commit}; `PYTHONPATH=src python3 experiments/h027_g2.py`; markets.parquet "
     f"{sha(os.path.join(DATA, 'h014', 'markets.parquet'))}, events.parquet {sha(os.path.join(D, 'events.parquet'))}",
     f"- división temporal (igual que H014): fecha objetivo < {SPLIT} → ajuste (mitad 1); ≥ {SPLIT} → evaluación (mitad 2). "
     "Variantes: 1 (t = 15:00 local, info ≤ t − 15 min, θ = 0.05, ventana de precio (t, t+10 min]).",
     f"- (ciudad, unidad) con distribución (≥ {h027.MIN_FIT} días válidos en mitad 1 y ciudad aprobada en G1): {len(dists)}",
     f"- mercados de mitad 2 evaluables (ciudad con modelo, M válido): {n_eval_all:,}; abiertos en t (start ≤ t < cierre): "
     f"{len(e):,} en {e.event_id.nunique():,} eventos; fallos de descarga de trades: {int(e.fail.sum())}",
     f"- mercados con compra taker YES en (t, t+10 min]: {int(e.px_yes.notna().sum()):,}; NO: {int(e.px_no.notna().sum()):,}",
     "", "## Distribución de R = máximo final − M (mitad 1)", "",
     "| ciudad | unidad | días | P(R=0) | P(R=1) | P(R=2) | P(R≥3) | máx R |", "|---|---|---|---|---|---|---|---|"]
for (c, u), (dist, n) in sorted(dists.items()):
    g3 = sum(p for r, p in dist.items() if r >= 3)
    L.append(f"| {c} | {u} | {n} | {dist.get(0, 0):.2f} | {dist.get(1, 0):.2f} | {dist.get(2, 0):.2f} | {g3:.2f} | {max(dist)} |")
L += ["", "## Resultado (mitad 2)", "",
      f"- apuestas: {len(b):,} en {b.event_id.nunique():,} eventos (ciudad-fecha) (YES {int((b.side == 'YES').sum())}, "
      f"NO {int((b.side == 'NO').sum())}); edge esperado medio {b.edge.mean()*100:.2f} c; precio medio {b.px.mean():.3f}",
      f"- **PnL medio por acción {b.pnl.mean()*100:+.3f} c (IC95% cluster evento {lo*100:+.3f} … {hi*100:+.3f})**; "
      f"PnL total {b.pnl.sum():+.2f} USD por 1 acción/apuesta; aciertos {(b.pnl > 0).mean():.1%}",
      f"- costes ×2 (comisión ×2 + deslizamiento extra = max(0.01, (pYES+pNO−1)/2)): {b.pnl2.mean()*100:+.3f} c "
      f"(IC95% {lo2*100:+.3f} … {hi2*100:+.3f})",
      f"- sin los 5 mejores eventos: n={len(b5):,}, {b5.pnl.mean()*100:+.3f} c (IC95% {lo5*100:+.3f} … {hi5*100:+.3f})",
      f"- por lado: " + "; ".join(f"{s}: n={len(g)}, {g.pnl.mean()*100:+.2f} c, aciertos {(g.pnl > 0).mean():.0%}"
                                  for s, g in b.groupby("side")),
      f"- por prob. del modelo (apuestas): " + "; ".join(
          f"{k}: n={len(g)}, {g.pnl.mean()*100:+.2f} c" for k, g in b.groupby(pd.cut(b.prob, [-0.001, 0.0, 0.5, 0.999, 1.0]), observed=True)),
      f"- tasa de comisión media {b.rate.mean():.3f} (h001.fee_rate; 0.07 si el mercado no expone feeSchedule)",
      f"- capital bloqueado: días medios hasta el cierre {b.days.mean():.2f} (mediana {b.days.median():.2f})",
      f"- **rentabilidad de cartera Σpnl/Σ(capital·días)·365 = {port:+.1%} (IC95% cluster {plo:+.1%} … {phi:+.1%})**; "
      f"con costes ×2: {port2:+.1%}",
      f"- con capital ocioso (banca = máximo capital simultáneo {peak:.2f} USD por 1 acción/apuesta, periodo completo): "
      f"{bank:+.1%} anual (las cifras anualizadas son enormes en valor absoluto porque el capital solo se bloquea ~0.4 días)",
      "", "## Probabilidad: modelo vs precio ejecutable", "",
      f"- mercados limpios con precio YES ejecutable en (t, t+10 min]: {len(q):,} en {q.event_id.nunique():,} eventos",
      f"- Brier modelo {((q.prob - q.y) ** 2).mean():.4f} vs precio {((q.px_yes - q.y) ** 2).mean():.4f}; diferencia "
      f"{q.d_brier.mean():+.4f} (IC95% cluster {blo:+.4f} … {bhi:+.4f})",
      f"- log loss (recorte 1e-3) modelo {ll(q.prob, q.y).mean():.4f} vs precio {ll(q.px_yes, q.y).mean():.4f}; diferencia "
      f"{q.d_ll.mean():+.4f} (IC95% {llo:+.4f} … {lhi:+.4f})",
      f"- Brier del modelo en todos los mercados limpios evaluables (n={len(ea):,}): {((ea.prob - ea.y) ** 2).mean():.4f}",
      "", "| prob. modelo | mercados | prob media | frecuencia YES |", "|---|---|---|---|"]
for k, g in ea.groupby(ea_bins, observed=True):
    L.append(f"| {k} | {len(g):,} | {g.prob.mean():.3f} | {g.y.mean():.3f} |")
L += ["", "## Por ciudad", "", "| ciudad | apuestas | eventos | PnL medio c |", "|---|---|---|---|"]
for c, g in b.groupby("city"):
    L.append(f"| {c} | {len(g)} | {g.event_id.nunique()} | {g.pnl.mean()*100:+.2f} |")
pred1 = lo > 0
pred2 = q.d_brier.mean() < 0
L += ["", "## Predicción falsable", "",
      f"- PnL > 0 con IC95% cluster (ciudad-fecha) > 0: **{'CUMPLIDA' if pred1 else 'NO cumplida'}**",
      f"- Brier modelo < Brier precio: **{'CUMPLIDA' if pred2 else 'NO cumplida'}** "
      f"({'mejora significativa' if bhi < 0 else ('el modelo es significativamente PEOR' if blo > 0 else 'diferencia no significativa')} al 95%)",
      f"- eventos independientes con apuesta: {b.event_id.nunique()} (G4 exigirá ≥ 150 en OOS)",
      "", "## Sustituciones", "",
      "1. Distribución por (ciudad, unidad): Londres tiene mercados en °C y °F; R se mide en la unidad del mercado.",
      "2. Días de capital bloqueado = closedTime − t (pesimista: el pago llega al cerrar el mercado, no al fin del día).",
      "3. Mercados ya cerrados o aún no creados en t se excluyen (conocido en t). Hong Kong (HKO) y Taipéi (CWA) excluidos "
      "por falta de METAR (ver reports/h027_g1.md).",
      f"4. Observación: {n_eval_all - len(e):,} de {n_eval_all:,} mercados evaluables ({1 - len(e) / n_eval_all:.0%}) ya estaban "
      "cerrados a las 15:00 locales: los tramos que el máximo acumulado deja muertos se resuelven pronto (horas), así que "
      f"la parte más obvia del nowcast no es operable (de los cerrados: {cl_y0:.1%} resolvieron NO; {cl_dead:.1%} tenían M > tramo "
      "a las 15:00). No se cuenta como variante."]
open(os.path.join(ROOT, "reports", "h027_g2.md"), "w").write("\n".join(L) + "\n")
b.drop(columns=[c for c in b.columns if c in ("start", "end")]).to_parquet(os.path.join(D, "g2_bets.parquet"))
print("\n".join(L))
