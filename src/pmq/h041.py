"""H041 — comprar el lado del DISPUTANTE (token opuesto al propuesto) tras la primera disputa UMA.

Reutiliza íntegramente H035 (horas de disputa on-chain, ventana, tope de precio, PnL); solo cambia el token.
"""
from pmq import h035


def disputer_side(proposed_price):
    """Índice del token opuesto a la propuesta disputada: 1e18 (propone outcome 0) → 1; 0 → 0; otro → None."""
    s = h035.side_of_price(proposed_price)
    return None if s is None else 1 - s


def entry(trades, proposed_price, t_dispute):
    """(idx, precio, motivo): peor compra taker del token del disputante en (t, t+2 h], t = disputa + 30 min."""
    idx = disputer_side(proposed_price)
    if idx is None:
        return None, None, "sin_lado"
    px, why = h035.entry(trades, idx, t_dispute)
    return idx, px, why


def pnl(idx, px, rate, y):
    return h035.pnl(idx, px, rate, y)
