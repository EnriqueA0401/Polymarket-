"""Tests H039: comisiones, orientación de exposiciones, pares por minuto, pagos y anti-lookahead (a mano)."""
import math
import numpy as np
import pandas as pd
import pytest

from pmq import h039 as A


def test_kalshi_fee_rounding():
    assert A.k_fee(0.5, 100) == pytest.approx(1.75)        # 0.07·100·0.25 = 1.75 exacto (sin céntimo extra por coma flotante)
    assert A.k_fee(0.5, 1) == pytest.approx(0.02)          # 1.75 c → 2 c
    assert A.k_fee(0.6, 100) == pytest.approx(1.68)
    assert A.k_fee(0.6, 10) == pytest.approx(0.17)         # 16.8 c → 17 c
    assert A.k_fee(0.01, 1) == pytest.approx(0.01)         # 0.0693 c → 1 c
    assert A.k_fee(0.5, 100, rate=0.035) == pytest.approx(0.88)


def test_pm_fee_and_pair_cost():
    assert A.pm_fee(0.4, 0.07) == pytest.approx(0.0168)
    # 0.50 + 0.45 + 1.75/100 + 0.07·0.45·0.55
    assert A.pair_cost(0.50, 0.45, 0.07, C=100) == pytest.approx(0.95 + 0.0175 + 0.017325)
    # C=1: la comisión de Kalshi redondea a 2 c
    assert A.pair_cost(0.50, 0.45, 0.07, C=1) == pytest.approx(0.95 + 0.02 + 0.017325)


def test_payoff_orientation():
    for e in (0, 1):
        assert A.pair_payoff(e, 1.0, 1.0) == 1.0           # gana team0 en ambas
        assert A.pair_payoff(e, 0.0, 0.0) == 1.0           # gana team1 en ambas
        assert A.pair_payoff(e, 0.5, 0.5) == 1.0           # 50-50 en ambas
    # aplazamiento largo: Kalshi liquida team0 a precio justo 0.6, PM espera y gana team1
    assert A.pair_payoff(0, 0.0, 0.6) == pytest.approx(1.6)
    assert A.pair_payoff(1, 0.0, 0.6) == pytest.approx(0.4)
    # discrepancia de resolución: PM dice team0, Kalshi team1
    assert A.pair_payoff(0, 1.0, 0.0) == 0.0
    assert A.pair_payoff(1, 1.0, 0.0) == 2.0


def kt(ts, side, yes, n):
    return {"created_time": pd.Timestamp(ts, unit="s", tz="UTC").isoformat(), "yes_price_dollars": f"{yes:.4f}",
            "count_fp": f"{n:.2f}", "taker_side": side}


def test_k_buys_orientation():
    t0 = A.k_buys([kt(60, "yes", 0.40, 5), kt(61, "no", 0.40, 7)], team=0)
    assert t0.exp.tolist() == [0, 1] and t0.price.tolist() == pytest.approx([0.40, 0.60]) and t0["size"].tolist() == [5, 7]
    assert t0.t.tolist() == pytest.approx([60, 61])
    t1 = A.k_buys([kt(60, "yes", 0.62, 1), kt(61, "no", 0.62, 1)], team=1)
    assert t1.exp.tolist() == [1, 0] and t1.price.tolist() == pytest.approx([0.62, 0.38])


def pmt(ts, side, idx, px, sz):
    return {"timestamp": ts, "side": side, "outcomeIndex": idx, "price": px, "size": sz}


def test_pm_buys_ignores_sells():
    b = A.pm_buys([pmt(10, "BUY", 1, 0.4, 3), pmt(11, "SELL", 0, 0.6, 3)])
    assert len(b) == 1 and b.exp.iloc[0] == 1


def synth():
    kb = A.k_buys([kt(600, "yes", 0.50, 10), kt(610, "yes", 0.52, 4),   # minuto 10: exp0 peor 0.52
                   kt(615, "no", 0.30, 8),                                  # minuto 10: exp1 a 0.70
                   kt(700, "yes", 0.55, 3)], team=0)                        # minuto 11: exp0
    pb = A.pm_buys([pmt(605, "BUY", 1, 0.45, 20), pmt(650, "BUY", 1, 0.46, 6),   # minuto 10: token1 peor 0.46
                    pmt(640, "BUY", 0, 0.29, 5),                                    # minuto 10: token0
                    pmt(800, "BUY", 1, 0.40, 9)])                                   # minuto 13: sin Kalshi
    return kb, pb


def test_pairs_by_hand():
    kb, pb = synth()
    p = A.pairs(kb, pb, gs=10_000, pm_rate=0.07, C=100).sort_values("e").reset_index(drop=True)
    assert len(p) == 2 and p.minute.tolist() == [10, 10] and p.e.tolist() == [0, 1]
    r0, r1 = p.iloc[0], p.iloc[1]
    # e=0: Kalshi 'gana team0' 0.52 + PM token1 0.46
    assert r0.pk == pytest.approx(0.52) and r0.pp == pytest.approx(0.46)
    assert r0.cost == pytest.approx(0.98 + A.k_fee(0.52, 100) / 100 + 0.07 * 0.46 * 0.54)
    assert r0.k_size == 14 and r0.pm_size == 26 and r0.k_size_w == 4 and r0.pm_size_w == 6
    assert r0["dt"] == pytest.approx(40)
    # e=1: Kalshi NO de team0 a 0.70 + PM token0 0.29
    assert r1.pk == pytest.approx(0.70) and r1.pp == pytest.approx(0.29)
    assert r1.profit == pytest.approx(1 - r1.cost)


def test_pairs_anti_lookahead():
    kb, pb = synth()
    base = A.pairs(kb, pb, gs=10_000, pm_rate=0.07)
    # trades después del inicio no cuentan
    kb2 = pd.concat([kb, pd.DataFrame({"t": [10_005.0], "exp": [0], "price": [0.01], "size": [1e6]})])
    pb2 = pd.concat([pb, pd.DataFrame({"t": [10_010.0], "exp": [1], "price": [0.01], "size": [1e6]})])
    pd.testing.assert_frame_equal(base, A.pairs(kb2, pb2, gs=10_000, pm_rate=0.07))
    # alterar el minuto 11 no cambia el par del minuto 10
    kb3 = kb.copy(); kb3.loc[kb3.t >= 660, "price"] = 0.99
    pd.testing.assert_frame_equal(base, A.pairs(kb3, pb, gs=10_000, pm_rate=0.07))
    # inicio a las 650 s: la compra PM de 650 s queda fuera → el peor token1 del minuto 10 es 0.45
    p = A.pairs(kb, pb, gs=650, pm_rate=0.07)
    assert p[p.e == 0].pp.iloc[0] == pytest.approx(0.45)


def test_pairs_empty():
    kb, pb = synth()
    assert len(A.pairs(kb.iloc[0:0], pb, gs=10_000, pm_rate=0.07)) == 0
    assert len(A.pairs(kb, pb, gs=0, pm_rate=0.07)) == 0


def test_k_asks_and_cost():
    book = {"yes_dollars": [["0.4000", "10"]], "no_dollars": [["0.4800", "100"], ["0.4900", "50"]]}
    asks = A.k_asks(book, "yes")
    assert asks == [(0.51, 50.0), (0.52, 100.0)]
    assert A.k_asks(book, "no") == [(0.6, 10.0)]
    # 50·0.51 + ceil(0.07·50·0.51·0.49 = 0.87465 → 0.88) + 50·0.52 + ceil(0.8736 → 0.88)
    assert A.k_buy_cost(asks, 100) == pytest.approx(25.5 + 0.88 + 26.0 + 0.88)
    assert math.isnan(A.k_buy_cost(asks, 200))


def test_null_random_pairs_cost_more_than_one():
    """Test nulo: con precios coherentes (pk + pp = 1 + medio spread) ningún par es oportunidad."""
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, 500)
    costs = [A.pair_cost(x + 0.005, 1 - x + 0.005, 0.07) for x in p]
    assert min(costs) > 1.0
