import pytest
from pmq import h013sim


def tr(i, s, p, t):
    return {"outcomeIndex": i, "side": s, "price": p, "timestamp": t}


def test_fill_y_pnl_a_mano():
    mids = [(0, 0.50), (60, 0.50)]
    trades = [tr(0, "SELL", 0.47, 10),       # cruza bid 0.48 en el minuto 0
              tr(0, "BUY", 0.52, 70),        # toca ask 0.52 sin cruzar: no fill
              tr(0, "BUY", 0.53, 80)]        # cruza ask en el minuto 1
    pnl, nb, na = h013sim.simulate(mids, trades, 0.04, 10, 1.0)
    assert (nb, na) == (1, 1)
    assert pnl == pytest.approx(10 * (1 - 0.48) + 10 * (0.52 - 1))


def test_trade_en_t_exacto_no_cuenta_para_ese_minuto():
    pnl, nb, na = h013sim.simulate([(60, 0.5)], [tr(0, "SELL", 0.40, 60)], 0.04, 10, 0.0)
    assert nb == 0
