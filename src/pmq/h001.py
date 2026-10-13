"""H001 — favorito-longshot. Construcción de observaciones y backtest.

Una observación = (mercado, horizonte h): precio YES observado en t = end − h usando
solo puntos con timestamp ≤ t (y ≥ t − MAX_STALE). Solo mercados abiertos en t.
"""
import numpy as np
import pandas as pd

HOLDOUT_START = pd.Timestamp("2026-04-12", tz="UTC")
MAX_STALE = pd.Timedelta("6h")
DEFAULT_FEE_RATE = 0.07   # pesimista si el mercado no expone feeSchedule
SPREAD_COST = 0.02        # medio spread + slippage por acción al entrar (reports/costs.md)


def price_at(history, t_unix, max_stale_s):
    """Último precio con ts ≤ t. None si no hay o está demasiado viejo."""
    best = None
    for pt in history:
        if pt["t"] <= t_unix and (best is None or pt["t"] > best["t"]):
            best = pt
    if best is None or t_unix - best["t"] > max_stale_s:
        return None
    return float(best["p"])


def observations(universe, histories, h):
    """universe: DataFrame del universo; histories: dict id -> lista {t,p}."""
    out = []
    for r in universe.itertuples():
        hist = histories.get(r.id)
        if not hist:
            continue
        t = r.end - h
        if not (r.start < t) or (pd.notna(r.closed_time) and r.closed_time <= t):
            continue
        p = price_at(hist, t.timestamp(), MAX_STALE.total_seconds())
        if p is None:
            continue
        close = r.closed_time if pd.notna(r.closed_time) else r.end
        out.append({"id": r.id, "event_id": r.event_id, "t": t, "p": p, "y": r.y,
                    "clean": r.clean, "close": close, "category": r.category,
                    "fee_rate": fee_rate(r.fee_schedule), "volume": r.volume})
    return pd.DataFrame(out)


def fee_rate(schedule_json):
    import json
    if isinstance(schedule_json, str) and schedule_json:
        try:
            return float(json.loads(schedule_json)["rate"])
        except (KeyError, ValueError, TypeError):
            pass
    return DEFAULT_FEE_RATE


def trades(obs, lo=0.10, hi=0.90, cost_mult=1.0):
    """Señal: p ≤ lo → comprar NO; p ≥ hi → comprar YES. Devuelve una fila por operación."""
    o = obs[(obs.p <= lo) | (obs.p >= hi)].copy()
    buy_yes = o.p >= hi
    tok_px = np.where(buy_yes, o.p, 1 - o.p)
    q = np.minimum(tok_px + SPREAD_COST * cost_mult, 0.999)
    fee = o.fee_rate.values * cost_mult * q * (1 - q)
    payoff = np.where(buy_yes, o.y, 1 - o.y)
    o["side"] = np.where(buy_yes, "YES", "NO")
    o["q"], o["fee"], o["payoff"] = q, fee, payoff
    o["ret"] = (payoff - q - fee) / (q + fee)
    days = ((o.close - o.t).dt.total_seconds() / 86400).clip(lower=1 / 24)
    o["days"] = days
    return o


def cluster_bootstrap(df, col="ret", cluster="event_id", n=2000, seed=0):
    """IC95% de la media de `col` remuestreando clusters."""
    rng = np.random.default_rng(seed)
    g = df.groupby(cluster)[col].agg(["sum", "count"])
    s, c = g["sum"].values, g["count"].values
    k = len(g)
    idx = rng.integers(0, k, size=(n, k))
    means = s[idx].sum(1) / c[idx].sum(1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def calibration(obs, bins=(0, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, 1.0001)):
    o = obs[obs.clean].copy()
    o["bin"] = pd.cut(o.p, bins, right=False)
    return o.groupby("bin", observed=True).agg(n=("y", "size"), p_mean=("p", "mean"), y_rate=("y", "mean"))
