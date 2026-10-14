import pytest
from pmq import h011


def test_fair_simetrias():
    assert h011.fair_candle(100, 100, 5, 0.001) == pytest.approx(0.5)
    assert h011.fair_twap(100, 100, 100, 0.5, 2.5, 0.001) == pytest.approx(0.5)
    assert h011.fair_candle(100, 101, 5, 0.001) > 0.9
    assert h011.fair_twap(100, 99, 99, 0.5, 2.5, 0.001) < 0.1


def test_twap_ventana_casi_completa_es_determinista():
    # w→1: TWAP ≈ media transcurrida
    assert h011.fair_twap(100, 100.5, 90, 1.0, 0, 0.01) == 1.0


def test_sigma():
    assert h011.sigma_1m([100, 100, 100, 100, 100, 100, 100]) == 0.0
