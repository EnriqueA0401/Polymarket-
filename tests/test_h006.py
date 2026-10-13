import pandas as pd
import pytest
from pmq import h006


def tr(i, s, px, ts):
    return {"outcomeIndex": i, "side": s, "price": px, "timestamp": ts}


def test_fill_estricto_lado_long():
    p = 0.05  # ofrecemos YES a 0.06
    assert not h006.filled([tr(0, "BUY", 0.06, 10)], "long", p, 0, 100)      # toca, no cruza
    assert h006.filled([tr(0, "BUY", 0.07, 10)], "long", p, 0, 100)
    assert h006.filled([tr(1, "SELL", 0.93, 10)], "long", p, 0, 100)         # vende NO bajo 0.94
    assert not h006.filled([tr(0, "BUY", 0.07, 200)], "long", p, 0, 100)     # fuera de ventana
    assert not h006.filled([tr(0, "BUY", 0.07, 0)], "long", p, 0, 100)       # en t0 exacto: antes de la orden


def test_fill_lado_fav():
    p = 0.95  # pujamos YES a 0.94
    assert h006.filled([tr(0, "SELL", 0.93, 5)], "fav", p, 0, 10)
    assert not h006.filled([tr(0, "SELL", 0.94, 5)], "fav", p, 0, 10)
    assert h006.filled([tr(1, "BUY", 0.07, 5)], "fav", p, 0, 10)


def test_pnl_a_mano():
    assert h006.pnl("long", 0.94, 0.0) == pytest.approx(0.06)
    assert h006.pnl("long", 0.94, 1.0) == pytest.approx(-0.94)
    assert h006.pnl("fav", 0.94, 1.0) == pytest.approx(0.06)
    assert h006.pnl("fav", 0.94, 0.5) == pytest.approx(-0.44)


def test_signals_niveles():
    o = pd.DataFrame({"p": [0.01, 0.05, 0.5, 0.95, 0.99]})
    s = h006.signals(o)
    assert s.side.tolist() == ["long", "fav"]
    assert s.level.tolist() == pytest.approx([0.94, 0.94])
