"""H040 [BIN] — binarias de pago fijo: acierto direccional a 5 min con reglas simples."""
import numpy as np
import pandas as pd

H = 5   # minutos


def breakeven(payout):
    """Acierto mínimo para EV ≥ 0 con pago `payout` (0.8 = 80%) y pérdida total si falla."""
    return 1 / (1 + payout)


def signals(close, rule):
    """Decisiones cada H minutos (bloques no solapados). Solo usa precios ≤ t.
    Devuelve DataFrame con t, dir (+1/−1/0) y resultado (1 acierto, 0 fallo; empate = fallo)."""
    c = close.values
    idx = np.arange(H, len(c) - H, H)
    past = np.sign(c[idx] - c[idx - H])
    fut = np.sign(c[idx + H] - c[idx])
    d = past if rule == "momentum" else -past
    ok = (d != 0)
    hit = ((d == fut) & (fut != 0)).astype(int)
    return pd.DataFrame({"t": close.index[idx][ok], "dir": d[ok], "hit": hit[ok]})
