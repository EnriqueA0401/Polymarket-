"""H035 G2 (solo entrenamiento, closedTime < 2026-04-12). Requiere experiments/h035_g1.py.

    PYTHONPATH=src python3 experiments/h035_g2.py --prefetch   (solo descarga trades, 3 hilos)
    PYTHONPATH=src python3 experiments/h035_g2.py              → reports/h035_g2.md

Protocolo pre-registrado (HYPOTHESES.md ### H035), 1 variante:
- universo: mercados de entrenamiento con disputa on-chain emparejada (G1) y propuesta 0/1.
- t = blockTimestamp de la primera DisputePrice + 30 min; lado = el propuesto originalmente.
- entrada = peor compra taker real de ese token en (t, t+2 h]; solo si ≤ 0.95. Hasta resolución.
- comisión vigente (feeSchedule; 0.07 si falta); clusters = evento.
"""
import hashlib, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h014, h027, h035, trades
from pmq.universe import DATA

D = os.path.join(DATA, "h035")
CACHE = os.path.join(DATA, "trades_h035")
W = h035.WINDOW_S
rng = np.random.default_rng(0)
EPOCH = pd.Timestamp(0, tz="UTC")

g = pd.read_parquet(os.path.join(D, "markets.parquet"))
assert (g.closed_time < h001.HOLDOUT_START).all()
m = g[g.matched & g.in_universe].copy()
n_match = len(m)
n_5050 = int(m.side.isna().sum())
m = m[m.side.notna()].copy()
m["side"] = m.side.astype(int)
m["t0"] = m.d_ts.astype(int) + h035.DELAY_S
m["event_id"] = m.event_id.fillna(m.g_event_id).astype(str)


def fetch_all(mm):
    with ThreadPoolExecutor(3) as ex:
        return list(ex.map(lambda r: trades.fetch(r[0], int(r[1]), int(r[1]) + W, CACHE), zip(mm.condition_id, mm.t0)))


if "--prefetch" in sys.argv:
    print("prefetch", len(m), flush=True)
    r = fetch_all(m)
    print("fallos", sum(x is None for x in r), flush=True)
    sys.exit()

res = fetch_all(m)
m["fail"] = [r is None for r in res]
m["n_tr"] = [len(r or []) for r in res]
e = [h035.entry(r, s, td) for r, s, td in zip(res, m.side, m.d_ts.astype(int))]
m["px"], m["why"] = zip(*e)
m["rate"] = [h001.fee_rate(x) for x in m.fee_schedule]
# precio del lado contrario en la misma ventana (diagnóstico de spread para costes ×2)
m["px_opp"] = [h035.h005.exec_price(r, 1 - s, t, t + W) for r, s, t in zip(res, m.side, m.t0)]
b = m[m.why == "ok"].copy()
b["px"] = b.px.astype(float)
b["pnl"] = [h035.pnl(s, p, r, y) for s, p, r, y in zip(b.side, b.px, b.rate, b.y)]
sd = lambda s: "YES" if s == 0 else "NO"
spread = (b.px + b.px_opp.astype(float) - 1) / 2
b["slip2"] = np.where(spread.notna(), np.maximum(spread.fillna(0), 0.01), 0.01)
b["pnl2"] = [h014.pnl(sd(s), p, r, y, 2.0, sl) for s, p, r, y, sl in zip(b.side, b.px, b.rate, b.y, b.slip2)]
b["cap"] = b.px + [h014.fee(p, r) for p, r in zip(b.px, b.rate)]
b["cap2"] = [min(p + s, 0.999) + 2 * h014.fee(min(p + s, 0.999), r) for p, s, r in zip(b.px, b.slip2, b.rate)]
b["days"] = ((b.closed_time - pd.to_datetime(b.t0, unit="s", utc=True)).dt.total_seconds() / 86400).clip(lower=1 / 24)
b["t_close"] = (b.closed_time - EPOCH) // pd.Timedelta(seconds=1)
b["win"] = np.where(b.side == 0, b.y, 1 - b.y)
# diagnóstico (no es la regla): precio mediano de las compras taker del lado propuesto en la ventana
rmap = dict(zip(m.index, res))
b["px_med"] = [float(np.median([float(x["price"]) for x in rmap[i] if x["outcomeIndex"] == s and x["side"] == "BUY"
                                and t < x["timestamp"] <= t + W])) for i, s, t in zip(b.index, b.side, b.t0)]
b["pnl_med"] = [h035.pnl(s, p, r, y) for s, p, r, y in zip(b.side, b.px_med, b.rate, b.y)]


def ci(df, col, cluster="event_id"):
    return h001.cluster_bootstrap(df, col=col, cluster=cluster) if len(df) else (np.nan, np.nan)


def ci_port(df, col="pnl", cap="cap", n=2000):
    dd = df.assign(cd=df[cap] * df.days)
    gg = dd.groupby("event_id").agg(a=(col, "sum"), c=("cd", "sum"))
    a, c = gg.a.values, gg.c.values
    idx = rng.integers(0, len(gg), (n, len(gg)))
    return np.percentile(a[idx].sum(1) / c[idx].sum(1) * 365, [2.5, 97.5])


nb = len(b)
nev = b.event_id.nunique()
lo, hi = ci(b, "pnl")
lo2, hi2 = ci(b, "pnl2")
top = b.groupby("event_id").pnl.sum().sort_values(ascending=False).index[:5]
b5 = b[~b.event_id.isin(top)]
lo5, hi5 = ci(b5, "pnl")
port = h027.portfolio_return(b.pnl, b.cap, b.days) if nb else np.nan
plo, phi = ci_port(b) if nb else (np.nan, np.nan)
port2 = h027.portfolio_return(b.pnl2, b.cap2, b.days) if nb else np.nan
bank, peak = h027.bankroll_return(b.pnl, b.cap, b.t0, b.t_close) if nb else (np.nan, np.nan)
# un mercado por evento (el primero en disputarse) para independencia
b1 = b.sort_values("d_ts").groupby("event_id").head(1)
lo1, hi1 = ci(b1, "pnl")
# Brier: precio pagado como prob. de que gane el lado propuesto
bc = b[b.clean.astype(bool)].copy()
bc["d_brier"] = (bc.px - bc.win) ** 2 - (bc.px.mean() - bc.win) ** 2

commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
f = lambda x: "nan" if x != x else f"{x*100:+.2f}"
why = m.why.value_counts()
L = ["# H035 G2 — comprar el lado propuesto tras la disputa UMA (solo entrenamiento)", "",
     f"- commit {commit}; `PYTHONPATH=src python3 experiments/h035_g1.py && PYTHONPATH=src python3 experiments/h035_g2.py`; "
     f"markets.parquet {sha(os.path.join(D, 'markets.parquet'))}",
     "- 1 variante (t = primera DisputePrice on-chain + 30 min; lado propuesto; peor compra taker real en (t, t+2 h]; "
     "precio ≤ 0.95; hasta resolución; comisión feeSchedule o 0.07).",
     f"- mercados emparejados en G1 y en el universo: {n_match:,}; propuesta 50-50/otra (sin lado): {n_5050}; "
     f"evaluados: {len(m):,} en {m.event_id.nunique():,} eventos; fallos de descarga: {int(m.fail.sum())}",
     f"- motivo de no entrada: " + "; ".join(f"{k}: {v:,}" for k, v in why.items()),
     "", "## Resultado", "",
     f"- operaciones: {nb:,} en **{nev:,} eventos** (lado propuesto YES/outcome0: {int((b.side == 0).sum())}, "
     f"NO/outcome1: {int((b.side == 1).sum())}); precio medio {b.px.mean():.3f}; anulados/50-50 {int((~b.clean.astype(bool)).sum())}",
     f"- tasa de acierto del lado propuesto (= 1 − reversión) en las operaciones: {b.win.mean():.1%} frente a precio medio "
     f"{b.px.mean():.1%}",
     f"- **PnL medio por acción {f(b.pnl.mean())} c (IC95% cluster evento {f(lo)} … {f(hi)})**; PnL total "
     f"{b.pnl.sum():+.2f} USD por 1 acción/operación",
     f"- diagnóstico optimista (precio = mediana de compras taker en la ventana, no la regla): "
     f"{f(b.pnl_med.mean())} c (IC95% {f(ci(b, 'pnl_med')[0])} … {f(ci(b, 'pnl_med')[1])})",
     f"- un mercado por evento (primera disputa): n={len(b1):,}, {f(b1.pnl.mean())} c (IC95% {f(lo1)} … {f(hi1)})",
     f"- costes ×2 (comisión ×2 + deslizamiento extra max(0.01, (p+p_opuesto−1)/2)): {f(b.pnl2.mean())} c "
     f"(IC95% {f(lo2)} … {f(hi2)})",
     f"- sin los 5 mejores eventos: n={len(b5):,}, {f(b5.pnl.mean())} c (IC95% {f(lo5)} … {f(hi5)})",
     "- por tramo de precio: " + "; ".join(
         f"{k}: n={len(x)}, acierto {x.win.mean():.0%}, {f(x.pnl.mean())} c"
         for k, x in b.groupby(pd.cut(b.px, [0, .2, .5, .8, .9, .95]), observed=True)),
     "- por lado propuesto: " + "; ".join(f"idx {s}: n={len(x)}, {f(x.pnl.mean())} c" for s, x in b.groupby("side")),
     "- negRisk: " + "; ".join(f"{k}: n={len(x)}, {f(x.pnl.mean())} c" for k, x in b.groupby("neg_risk")),
     "- por trimestre de disputa: " + "; ".join(
         f"{k}: n={len(x)}, {f(x.pnl.mean())} c" for k, x in b.groupby(b.d_time.dt.tz_localize(None).dt.to_period("Q").astype(str))),
     f"- comisión media {b.rate.mean():.3f}; días de capital (t → closedTime): mediana {b.days.median():.2f}, media {b.days.mean():.2f}",
     f"- **rentabilidad de cartera Σpnl/Σ(capital·días)·365 = {port:+.1%} (IC95% cluster {plo:+.1%} … {phi:+.1%})**; "
     f"costes ×2: {port2:+.1%}; con capital ocioso (banca = máx. capital simultáneo {peak:.2f} USD/acción): {bank:+.1%} anual",
     f"- Brier del precio pagado (lado propuesto) {((bc.px - bc.win) ** 2).mean():.4f} en {len(bc):,} limpios",
     "", "## Predicción falsable", "",
     f"- PnL > 0 con IC95% cluster > 0: **{'CUMPLIDA' if lo > 0 else 'NO cumplida'}**",
     f"- ≥ 150 eventos: **{'SÍ' if nev >= 150 else 'NO'}** ({nev})",
     "", "## Sustituciones y notas", "",
     "1. Hora de disputa = blockTimestamp del log DisputePrice (OOv2/MOOv2 en Polygon), emparejado por "
     "questionID = keccak256(ancillaryData). Sin sustitutos: mercados sin log emparejado se excluyen (ver G1).",
     "2. Días de capital desde t (inicio de ventana; pesimista) hasta closedTime de Gamma.",
     "3. Precio = peor compra taker del token propuesto en la ventana (no hay historial de libro); no se supone fill limit.",
     "4. Mercados resueltos 50-50 pagan 0.5 y se mantienen.",
     ]
open(os.path.join(ROOT, "reports", "h035_g2.md"), "w").write("\n".join(L) + "\n")
b.to_parquet(os.path.join(D, "g2_trades.parquet"))
print("\n".join(L))
