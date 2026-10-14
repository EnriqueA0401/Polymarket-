import pytest
from pmq import h013


def lv(p, s):
    return {"price": str(p), "size": str(s)}


def test_side_score_cuadratico():
    # v = 0.04, orden a 0.02 del mid → ((0.04−0.02)/0.04)² = 0.25
    assert h013.side_score([lv(0.48, 100)], 0.50, 0.04, True) == pytest.approx(25)
    assert h013.side_score([lv(0.45, 100)], 0.50, 0.04, True) == 0       # fuera de v


def test_expected_sin_competencia():
    book = {"bids": [lv(0.49, 1)], "asks": [lv(0.51, 1)]}
    e = h013.expected(book, rate=10, v_cents=40, min_size=100)   # v=0.40: competencia casi nula
    assert e["share"] == pytest.approx(25 / (25 + 0.975 ** 2)) and e["reward_day"] == pytest.approx(10 * e["share"])
    assert e["capital"] == pytest.approx(100 * 0.30 + 100 * (1 - 0.70))


def test_merge_complemento():
    m = h013.merge({"bids": [lv(0.4, 1)], "asks": []}, {"bids": [lv(0.5, 2)], "asks": [lv(0.7, 3)]})
    assert {x["price"] for x in m["bids"]} == {"0.4", str(1 - 0.7)}
    assert m["asks"][0]["price"] == "0.5"
