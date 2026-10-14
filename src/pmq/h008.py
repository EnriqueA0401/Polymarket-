"""H008 — seguir wallets rentables. Funciones puras (formación y copia)."""
import numpy as np
import pandas as pd

MIN_TRADES, MIN_EVENTS, TOP_K = 20, 10, 50
DELAY, WINDOW = 60, 600


def trade_pnl(side, outcome_index, price, size, y):
    """PnL realizado a resolución de un trade taker. y = pago del token 0 (YES)."""
    pay = y if outcome_index == 0 else 1 - y
    return size * (pay - price) if side == "BUY" else size * (price - pay)


def rank_wallets(tr):
    """tr: DataFrame con proxyWallet, pnl, event_id. Devuelve ranking de elegibles."""
    g = tr.groupby("proxyWallet").agg(pnl=("pnl", "sum"), n=("pnl", "size"), ev=("event_id", "nunique"))
    g = g[(g.n >= MIN_TRADES) & (g.ev >= MIN_EVENTS)]
    g["score"] = g.pnl / np.sqrt(g.n)
    return g.sort_values("score", ascending=False)


def copy_price(trades, idx, t0):
    """Peor precio de compra taker real del token `idx` (outcomeIndex) en (t0+DELAY, t0+DELAY+WINDOW]."""
    a, b = t0 + DELAY, t0 + DELAY + WINDOW
    px = [float(x["price"]) for x in trades or []
          if x["outcomeIndex"] == idx and x["side"] == "BUY" and a < x["timestamp"] <= b]
    return max(px) if px else None
