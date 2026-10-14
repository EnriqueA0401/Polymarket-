"""H005 — Polymarket vs Pinnacle pre-partido (fútbol). Decisión y PnL."""
import numpy as np

THETA = 0.03


def exec_price(trades, idx, t0, t1):
    """Peor (máximo) precio pagado por takers compradores del token `idx` en (t0, t1]. None si no hay."""
    px = [float(x["price"]) for x in trades or []
          if x["outcomeIndex"] == idx and x["side"] == "BUY" and t0 < x["timestamp"] <= t1]
    return max(px) if px else None


def fee(px, rate):
    return rate * px * (1 - px)


def decide(fair_yes, px_yes, px_no, rate, theta=THETA):
    """Devuelve ('YES'|'NO'|None, precio, edge). Edge neto de comisión por acción."""
    best = (None, np.nan, -np.inf)
    if px_yes is not None:
        e = fair_yes - px_yes - fee(px_yes, rate)
        if e > best[2]:
            best = ("YES", px_yes, e)
    if px_no is not None:
        e = (1 - fair_yes) - px_no - fee(px_no, rate)
        if e > best[2]:
            best = ("NO", px_no, e)
    return best if best[2] >= theta else (None, np.nan, best[2])


def pnl(side, px, rate, y):
    payoff = y if side == "YES" else 1 - y
    return payoff - px - fee(px, rate)
