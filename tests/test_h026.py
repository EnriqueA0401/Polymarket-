import pytest
from pmq import h026


def test_portfolio_return_a_mano():
    # 2 posiciones de 1 USD: +0.05 en 90 días y −1 en 10 días
    r = h026.portfolio_return([0.05, -1.0], [1.0, 1.0], [90, 10])
    assert r == pytest.approx((0.05 - 1.0) / (90 + 10) * 365)
    # una sola ganadora: 5% en 73 días = 25% anual simple
    assert h026.portfolio_return([0.05], [1.0], [73]) == pytest.approx(0.25)
