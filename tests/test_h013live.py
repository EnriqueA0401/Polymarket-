import pytest
from pmq import h013live as L


def tr(i, s, p):
    return {"outcomeIndex": i, "side": s, "price": p, "timestamp": 1}


def test_crossed_estricto_y_complemento():
    assert L.crossed([tr(0, "SELL", 0.48)], 0.48, 0.52) == (False, False)
    assert L.crossed([tr(0, "SELL", 0.47)], 0.48, 0.52) == (True, False)
    assert L.crossed([tr(1, "BUY", 0.53)], 0.48, 0.52) == (True, False)    # comprar NO a 0.53 ≡ vender YES a 0.47
    assert L.crossed([tr(1, "SELL", 0.47)], 0.48, 0.52) == (False, True)   # vender NO a 0.47 ≡ comprar YES a 0.53


def test_settle_a_mano():
    m = {"pos_yes": 20, "cost_yes": 20 * 0.48, "pos_no": 20, "cost_no": 20 * 0.48}
    assert L.settle(m, 1.0) == pytest.approx(20 - 9.6 - 9.6)
    assert L.settle(m, 0.0) == pytest.approx(20 - 19.2)
