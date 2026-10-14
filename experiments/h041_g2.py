"""H041 G2 (solo entrenamiento, closedTime < 2026-04-12). Requiere experiments/h035_g1.py.

    PYTHONPATH=src python3 experiments/h041_g2.py   → reports/h041_g2.md

Protocolo pre-registrado (HYPOTHESES.md ### H041), 1 variante: igual que H035 (mismos mercados y horas de
disputa on-chain, t = primera DisputePrice + 30 min) pero comprando el token OPUESTO al propuesto: peor
compra taker real en (t, t+2 h]; solo si ≤ 0.95; hasta resolución; comisión vigente; clusters = evento.
Éxito G2: PnL > 0 con IC95% > 0, costes×2 > 0, sin top-5 > 0.
`evaluate` y `summary` se reutilizan sin cambios en experiments/h041_g3.py (holdout).
"""
import hashlib, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h005, h014, h027, h035, h041, trades
from pmq.universe import DATA

D = os.path.join(DATA, "h035")
CACHE = os.path.join(DATA, "trades_h035")
W = h035.WINDOW_S
EPOCH = pd.Timestamp(0, tz="UTC")


def evaluate(m, cache=CACHE):
    """m: mercados con d_ts, d_proposed_price (str), condition_id, y, clean, fee_schedule, closed_time, event_id.
    Devuelve (m con motivo, b = operaciones con pnl/pnl2/cap/days)."""
    m = m.copy()
    m["t0"] = m.d_ts.astype(int) + h035.DELAY_S
    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(lambda r: trades.fetch(r[0], int(r[1]), int(r[1]) + W, cache), zip(m.condition_id, m.t0)))
    m["fail"] = [r is None for r in res]
    e = [h041.entry(r, int(p), int(td)) for r, p, td in zip(res, m.d_proposed_price, m.d_ts)]
    m["side"], m["px"], m["why"] = zip(*e)
    m["rate"] = [h001.fee_rate(x) for x in m.fee_schedule]
    m["px_opp"] = [h005.exec_price(r, 1 - s, t, t + W) if s is not None else None
                   for r, s, t in zip(res, m.side, m.t0)]
    b = m[m.why == "ok"].copy()
    b["side"] = b.side.astype(int)
    b["px"] = b.px.astype(float)
    b["pnl"] = [h041.pnl(s, p, r, y) for s, p, r, y in zip(b.side, b.px, b.rate, b.y)]
    sd = lambda s: "YES" if s == 0 else "NO"
    spread = (b.px + b.px_opp.astype(float) - 1) / 2
    b["slip2"] = np.where(spread.notna(), np.maximum(spread.fillna(0), 0.01), 0.01)
    b["pnl2"] = [h014.pnl(sd(s), p, r, y, 2.0, sl) for s, p, r, y, sl in zip(b.side, b.px, b.rate, b.y, b.slip2)]
    b["cap"] = b.px + [h014.fee(p, r) for p, r in zip(b.px, b.rate)]
    b["cap2"] = [min(p + s, 0.999) + 2 * h014.fee(min(p + s, 0.999), r) for p, s, r in zip(b.px, b.slip2, b.rate)]
    b["days"] = ((b.closed_time - pd.to_datetime(b.t0, unit="s", utc=True)).dt.total_seconds() / 86400).clip(lower=1 / 24)
    b["t_close"] = (b.closed_time - EPOCH) // pd.Timedelta(seconds=1)
    b["win"] = np.where(b.side == 0, b.y, 1 - b.y)
    return m, b


def ci(df, col, cluster="event_id"):
    return h001.cluster_bootstrap(df, col=col, cluster=cluster) if len(df) else (np.nan, np.nan)


def ci_port(df, col="pnl", cap="cap", n=2000, seed=0):
    rng = np.random.default_rng(seed)
    dd = df.assign(cd=df[cap] * df.days)
    gg = dd.groupby("event_id").agg(a=(col, "sum"), c=("cd", "sum"))
    a, c = gg.a.values, gg.c.values
    idx = rng.integers(0, len(gg), (n, len(gg)))
    return np.percentile(a[idx].sum(1) / c[idx].sum(1) * 365, [2.5, 97.5])


def summary(m, b):
    """Métricas y líneas de informe idénticas para G2 y G3."""
    f = lambda x: "nan" if x != x else f"{x*100:+.2f}"
    nb, nev = len(b), b.event_id.nunique()
    lo, hi = ci(b, "pnl")
    lo2, hi2 = ci(b, "pnl2")
    top = b.groupby("event_id").pnl.sum().sort_values(ascending=False).index[:5]
    b5 = b[~b.event_id.isin(top)]
    lo5, hi5 = ci(b5, "pnl")
    b1 = b.sort_values("d_ts").groupby("event_id").head(1)
    lo1, hi1 = ci(b1, "pnl")
    port = h027.portfolio_return(b.pnl, b.cap, b.days) if nb else np.nan
    plo, phi = ci_port(b) if nb else (np.nan, np.nan)
    port2 = h027.portfolio_return(b.pnl2, b.cap2, b.days) if nb else np.nan
    bank, peak = h027.bankroll_return(b.pnl, b.cap, b.t0, b.t_close) if nb else (np.nan, np.nan)
    why = m.why.value_counts()
    r = dict(n=nb, ev=nev, pnl=b.pnl.mean(), lo=lo, hi=hi, pnl2=b.pnl2.mean(), lo2=lo2, hi2=hi2,
             pnl5=b5.pnl.mean(), lo5=lo5, hi5=hi5, port=port, plo=plo, phi=phi)
    L = [f"- mercados evaluados: {len(m):,} en {m.event_id.nunique():,} eventos; fallos de descarga: {int(m.fail.sum())}",
         "- motivo de no entrada: " + "; ".join(f"{k}: {v:,}" for k, v in why.items()),
         "", "## Resultado", "",
         f"- operaciones: {nb:,} en **{nev:,} eventos** (token comprado outcome0/YES: {int((b.side == 0).sum())}, "
         f"outcome1/NO: {int((b.side == 1).sum())}); precio medio {b.px.mean():.3f}; anulados/50-50 {int((~b.clean.astype(bool)).sum())}",
         f"- tasa de acierto del lado del disputante: {b.win.mean():.1%} frente a precio medio {b.px.mean():.1%}",
         f"- **PnL medio por acción {f(b.pnl.mean())} c (IC95% cluster evento {f(lo)} … {f(hi)})**; PnL total "
         f"{b.pnl.sum():+.2f} USD por 1 acción/operación",
         f"- un mercado por evento (primera disputa): n={len(b1):,}, {f(b1.pnl.mean())} c (IC95% {f(lo1)} … {f(hi1)})",
         f"- **costes ×2** (comisión ×2 + deslizamiento extra max(0.01, (p+p_opuesto−1)/2)): {f(b.pnl2.mean())} c "
         f"(IC95% {f(lo2)} … {f(hi2)})",
         f"- **sin los 5 mejores eventos**: n={len(b5):,}, {f(b5.pnl.mean())} c (IC95% {f(lo5)} … {f(hi5)})",
         "- por tramo de precio: " + "; ".join(
             f"{k}: n={len(x)}, acierto {x.win.mean():.0%}, {f(x.pnl.mean())} c"
             for k, x in b.groupby(pd.cut(b.px, [0, .2, .5, .8, .9, .95]), observed=True)),
         "- por token comprado: " + "; ".join(f"idx {s}: n={len(x)}, {f(x.pnl.mean())} c" for s, x in b.groupby("side")),
         "- negRisk: " + "; ".join(f"{k}: n={len(x)}, {f(x.pnl.mean())} c" for k, x in b.groupby("neg_risk")),
         "- por trimestre de disputa: " + "; ".join(
             f"{k}: n={len(x)}, {f(x.pnl.mean())} c"
             for k, x in b.groupby(pd.to_datetime(b.d_ts, unit="s").dt.to_period("Q").astype(str))),
         f"- comisión media {b.rate.mean():.3f}; días de capital (t → closedTime): mediana {b.days.median():.2f}, media {b.days.mean():.2f}",
         f"- **rentabilidad de cartera Σpnl/Σ(capital·días)·365 = {port:+.1%} (IC95% cluster {plo:+.1%} … {phi:+.1%})**; "
         f"costes ×2: {port2:+.1%}; con capital ocioso (banca = máx. capital simultáneo {peak:.2f} USD/acción): {bank:+.1%} anual"]
    return r, L


def train_markets():
    g = pd.read_parquet(os.path.join(D, "markets.parquet"))
    assert (g.closed_time < h001.HOLDOUT_START).all()
    m = g[g.matched & g.in_universe].copy()
    m["event_id"] = m.event_id.fillna(m.g_event_id).astype(str)
    return m


if __name__ == "__main__":
    m0 = train_markets()
    m, b = evaluate(m0)
    r, body = summary(m, b)
    ok = r["lo"] > 0 and r["pnl2"] > 0 and r["pnl5"] > 0
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    f = lambda x: f"{x*100:+.2f}"
    L = ["# H041 G2 — comprar el lado del DISPUTANTE tras la disputa UMA (solo entrenamiento)", "",
         f"- commit {commit}; `PYTHONPATH=src python3 experiments/h035_g1.py && PYTHONPATH=src python3 experiments/h041_g2.py`; "
         f"markets.parquet {sha(os.path.join(D, 'markets.parquet'))}",
         "- 1 variante (mismos mercados y horas de disputa que H035; token opuesto al propuesto; peor compra taker real en "
         "(t, t+2 h], t = disputa + 30 min; precio ≤ 0.95; hasta resolución; comisión feeSchedule o 0.07).",
         "- AVISO: hipótesis diseñada tras ver H035 en entrenamiento; el veredicto solo vale en el holdout (G3).",
         ] + body + ["", "## Criterios de éxito G2 (pre-registrados)", "",
         f"- PnL > 0 con IC95% > 0: **{'SÍ' if r['lo'] > 0 else 'NO'}** ({f(r['pnl'])} c, IC {f(r['lo'])} … {f(r['hi'])})",
         f"- costes ×2 > 0: **{'SÍ' if r['pnl2'] > 0 else 'NO'}** ({f(r['pnl2'])} c)",
         f"- sin top-5 > 0: **{'SÍ' if r['pnl5'] > 0 else 'NO'}** ({f(r['pnl5'])} c)",
         f"- **G2 {'SUPERADO → se habilita G3 (holdout, una vez)' if ok else 'NO superado → el holdout NO se toca'}**",
         "", "## Notas", "",
         "1. Datos, emparejamiento y verificación precio→token: reports/h035_g1.md (100% emparejado, 100% concordancia).",
         "2. Los trades en caché de H035 contienen ambos tokens de la misma ventana; no hay descarga nueva.",
         "3. Propuestas 50-50/otras (sin lado) excluidas; mercados resueltos 50-50 pagan 0.5 y se mantienen."]
    open(os.path.join(ROOT, "reports", "h041_g2.md"), "w").write("\n".join(L) + "\n")
    b.to_parquet(os.path.join(DATA, "h035", "h041_g2_trades.parquet"))
    print("\n".join(L))
