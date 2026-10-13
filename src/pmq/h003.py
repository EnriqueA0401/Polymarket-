"""H003 — sobreprecio de "Yes". Reutiliza la muestra y observaciones de H001."""
import numpy as np
import pandas as pd

from pmq import h001


def traded_before(history, t_unix, window_s=86400):
    """True si hay ≥ 2 precios distintos en (t − window, t]. Solo usa datos ≤ t."""
    ps = {pt["p"] for pt in history if t_unix - window_s < pt["t"] <= t_unix}
    return len(ps) >= 2


def observations(universe, histories, h):
    obs = h001.observations(universe, histories, h)
    if obs.empty:
        return obs
    ok = [traded_before(histories[i], t.timestamp()) for i, t in zip(obs.id, obs.t)]
    obs = obs[np.array(ok, dtype=bool)]
    kind = universe.set_index("id").outcome0.reindex(obs.id).values
    return obs.assign(yesno=(kind == "Yes"))


def trades(obs, lo=0.20, hi=0.80, cost_mult=1.0):
    """Comprar NO cuando lo ≤ p ≤ hi."""
    o = obs[(obs.p >= lo) & (obs.p <= hi)].copy()
    q = np.minimum(1 - o.p + h001.SPREAD_COST * cost_mult, 0.999)
    fee = o.fee_rate.values * cost_mult * q * (1 - q)
    o["q"], o["fee"], o["payoff"] = q, fee, 1 - o.y
    o["ret"] = (o.payoff - q - fee) / (q + fee)
    return o
