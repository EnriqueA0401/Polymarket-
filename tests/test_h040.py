import pandas as pd
import pytest
from pmq import h040


def test_breakeven():
    assert h040.breakeven(0.8) == pytest.approx(1 / 1.8)
    assert h040.breakeven(0.9) == pytest.approx(1 / 1.9)


def test_signals_a_mano_y_sin_lookahead():
    idx = pd.date_range("2025-01-01", periods=20, freq="min", tz="UTC")
    close = pd.Series(list(range(20)), index=idx, dtype=float)       # tendencia perfecta
    m = h040.signals(close, "momentum"); r = h040.signals(close, "reversal")
    assert m.hit.mean() == 1.0 and r.hit.mean() == 0.0
    # cambiar el futuro no cambia las decisiones (dir) en t
    c2 = close.copy(); c2.iloc[-3:] = -100
    assert h040.signals(c2, "momentum").dir.tolist()[:2] == m.dir.tolist()[:2]
