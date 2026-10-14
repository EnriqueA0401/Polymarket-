import pytest

from pmq import h035, h041

ONE = 10 ** 18


def T(idx, px, ts, side="BUY"):
    return {"outcomeIndex": idx, "side": side, "price": px, "size": 10, "timestamp": ts}


def test_disputer_side_is_opposite_token():
    assert h041.disputer_side(ONE) == 1          # propuesto outcome 0 (YES) → compra token NO
    assert h041.disputer_side(0) == 0            # propuesto outcome 1 (NO) → compra token YES
    assert h041.disputer_side(ONE // 2) is None  # 50-50: sin lado
    assert h041.disputer_side(-(2 ** 255)) is None
    for p in (0, ONE):
        assert h041.disputer_side(p) == 1 - h035.side_of_price(p)


def test_entry_uses_opposite_token_prices():
    td = 1_000_000
    t0 = td + h035.DELAY_S
    tr = [T(0, 0.80, t0 + 10), T(1, 0.25, t0 + 10), T(1, 0.30, t0 + 20), T(1, 0.90, t0 + h035.WINDOW_S + 1)]
    assert h041.entry(tr, ONE, td) == (1, 0.30, "ok")     # YES propuesto → peor compra NO en ventana
    assert h041.entry(tr, 0, td) == (0, 0.80, "ok")       # NO propuesto → peor compra YES
    assert h041.entry(tr, ONE // 2, td) == (None, None, "sin_lado")


def test_pnl_disputer_hand():
    # YES propuesto, se compra NO a 0.30 con comisión 0.05; resultado final NO (y=0) → 1 − 0.30 − 0.05·0.3·0.7
    idx, px, _ = h041.entry([T(1, 0.30, 1_000_000 + h035.DELAY_S + 5)], ONE, 1_000_000)
    assert h041.pnl(idx, px, 0.05, 0.0) == pytest.approx(0.6895)
    assert h041.pnl(idx, px, 0.05, 1.0) == pytest.approx(-0.3105)
