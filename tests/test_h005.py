import pytest
from pmq import h005


def tr(i, s, px, ts):
    return {"outcomeIndex": i, "side": s, "price": px, "timestamp": ts}


def test_exec_price_peor_y_sin_futuro():
    t = [tr(0, "BUY", 0.40, 5), tr(0, "BUY", 0.45, 8), tr(0, "BUY", 0.90, 20), tr(0, "SELL", 0.50, 6)]
    assert h005.exec_price(t, 0, 0, 10) == 0.45
    assert h005.exec_price(t, 1, 0, 10) is None


def test_decide_y_pnl_a_mano():
    side, px, e = h005.decide(0.55, 0.50, 0.52, 0.0)
    assert side == "YES" and e == pytest.approx(0.05)
    assert h005.pnl("YES", 0.50, 0.0, 1.0) == pytest.approx(0.5)
    side, px, e = h005.decide(0.30, 0.31, 0.60, 0.05)
    assert side == "NO" and e == pytest.approx(0.70 - 0.60 - 0.05 * 0.6 * 0.4)
    assert h005.decide(0.50, 0.49, 0.50, 0.0)[0] is None   # edge 0.01 < θ
