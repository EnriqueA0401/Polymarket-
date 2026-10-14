"""H004 — favoritos casi decididos cerca del cierre."""
import numpy as np

LO, HI = 0.95, 0.995


def fav_side(p):
    """Lado favorito según precio YES en t (prices-history): 0 = YES, 1 = NO, None."""
    if p >= LO:
        return 0
    if p <= 1 - LO:
        return 1
    return None


def tradable(px):
    return px is not None and LO <= px < HI


def pnl(idx, px, rate, y):
    pay = y if idx == 0 else 1 - y
    return pay - px - rate * px * (1 - px)


def drop_top(df, col="pnl", cluster="event_id", k=5):
    """Media de `col` tras quitar los k clusters con mayor suma (test de robustez G4)."""
    s = df.groupby(cluster)[col].sum().sort_values(ascending=False)
    return df[~df[cluster].isin(s.index[:k])][col].mean()
