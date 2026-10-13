"""H006 — maker en extremos con fills pesimistas a partir de trades taker reales."""
import numpy as np
import pandas as pd

OFFSET = 0.01


def signals(obs):
    """Lado 'long' (vender YES longshot = pujar NO) y 'fav' (pujar YES favorito)."""
    o = obs.copy()
    o["side"] = np.where((o.p > .02) & (o.p <= .10), "long", np.where((o.p >= .90) & (o.p < .98), "fav", None))
    o = o[o.side.notna()].copy()
    o["level"] = np.where(o.side == "long", 1 - (o.p + OFFSET), o.p - OFFSET)  # precio de NUESTRA compra (NO o YES)
    return o


def filled(trades, side, p, t0, t1):
    """True si algún trade taker en (t0, t1] cruzó ESTRICTAMENTE nuestro nivel.
    outcomeIndex 0 = primer resultado (YES), 1 = segundo (NO)."""
    for x in trades or []:
        if not (t0 < x["timestamp"] <= t1):
            continue
        i, s, px = x["outcomeIndex"], x["side"], float(x["price"])
        if side == "long":   # nuestra puja de NO a 1-(p+off) ≡ oferta de YES a p+off
            if (i == 0 and s == "BUY" and px > p + OFFSET) or (i == 1 and s == "SELL" and px < 1 - (p + OFFSET)):
                return True
        else:                # nuestra puja de YES a p-off ≡ oferta de NO a 1-(p-off)
            if (i == 0 and s == "SELL" and px < p - OFFSET) or (i == 1 and s == "BUY" and px > 1 - (p - OFFSET)):
                return True
    return False


def pnl(side, level, y):
    """Por acción, sin comisión (maker). y = pago del YES (1, 0 o 0.5 anulado)."""
    payoff = (1 - y) if side == "long" else y
    return payoff - level
