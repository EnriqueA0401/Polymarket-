import math
import pandas as pd
import pytest
from pmq import h002


def bk(*asks):
    return {"asks": [{"price": str(p), "size": str(s)} for p, s in asks]}


def test_buy_cost_barrido_y_comision():
    b = bk((0.30, 5), (0.32, 100))
    c = h002.buy_cost(b, 10, 0.0)
    assert c == pytest.approx(5 * 0.30 + 5 * 0.32)
    c2 = h002.buy_cost(b, 10, 0.05)
    assert c2 == pytest.approx(c + 0.05 * (5 * 0.3 * 0.7 + 5 * 0.32 * 0.68))


def test_sin_profundidad_es_nan():
    assert math.isnan(h002.buy_cost(bk((0.5, 3)), 10, 0.0))


def test_analyse_arbitraje_conocido():
    ms = [{"acceptingOrders": True, "closed": False, "clobTokenIds": f'["y{i}", "n{i}"]', "feesEnabled": False}
          for i in range(3)]
    ev = {"id": "e", "markets": ms, "endDate": "2030-01-01T00:00:00Z"}
    books = {f"y{i}": bk((0.30, 1000)) for i in range(3)} | {f"n{i}": bk((0.70, 1000)) for i in range(3)}
    r = h002.analyse(ev, books, pd.Timestamp("2029-12-01", tz="UTC"))
    assert r["A_ret_10"] == pytest.approx((10 - 9) / 9)          # 3×0.30 por acción, paga 1
    assert r["B_ret_10"] == pytest.approx((20 - 21) / 21)        # 3×0.70, paga n−1 = 2


def test_safe_a_requiere_inactivos_resueltos_no():
    act = [{"acceptingOrders": True, "closed": False, "clobTokenIds": f'["y{i}", "n{i}"]'} for i in range(2)]
    books = {f"y{i}": bk((0.3, 100)) for i in range(2)} | {f"n{i}": bk((0.7, 100)) for i in range(2)}
    ts = pd.Timestamp("2029-12-01", tz="UTC")
    ok = {"id": "e", "markets": act + [{"closed": True, "outcomePrices": '["0", "1"]'}], "endDate": "2030-01-01T00:00:00Z"}
    bad = {"id": "e", "markets": act + [{"closed": True, "outcomePrices": '["1", "0"]'}], "endDate": "2030-01-01T00:00:00Z"}
    aug = {**ok, "negRiskAugmented": True}
    assert h002.analyse(ok, books, ts)["safe_a"] is True
    assert h002.analyse(bad, books, ts)["safe_a"] is False
    assert h002.analyse(aug, books, ts)["safe_a"] is False


def test_conversion_no_a_yes():
    ms = [{"acceptingOrders": True, "closed": False, "clobTokenIds": f'["y{i}", "n{i}"]', "feesEnabled": False}
          for i in range(3)]
    ev = {"id": "e", "markets": ms}
    bids = lambda p: {"bids": [{"price": str(p), "size": "1000"}]}
    books = {"y0": bids(0.45), "y1": bids(0.40), "y2": bids(0.30), "n0": bk((0.62, 1000)), "n1": bk((0.67, 1000)), "n2": bk((0.75, 1000))}
    r = h002.conversion(ev, books, pd.Timestamp("2030-01-01", tz="UTC"))
    # i=2: vender YES0+YES1 = 0.85·50 = 42.5, comprar NO2 = 37.5 → +5.0
    assert r["best_i"] == 2 and r["profit_50"] == pytest.approx(5.0)
