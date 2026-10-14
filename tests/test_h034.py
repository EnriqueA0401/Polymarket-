import copy

import pytest

from pmq import h034

DESC = ("If Game 3 is not played because the series result has already been determined "
        "(e.g., a team clinches the series before Game 3 is needed), this market will resolve to 50-50.")


def tr(ts, p, side="BUY", k=0, size=10.0):
    return {"timestamp": ts, "price": p, "side": side, "outcomeIndex": k, "size": size}


def test_parsing():
    assert h034.best_of("LoL: A vs B (BO5) - LCK") == 5
    assert h034.best_of("LoL: A vs B - LCK") is None
    assert h034.game_number("Game 3: Any Player Rampage?") == 3
    assert h034.game_number("Dota 2: A vs B - Game 3 Winner") == 3
    assert h034.game_number("Map 5: Odd/Even Total Rounds?") == 5
    assert h034.game_number("Game Handicap: A (-1.5)") is None
    assert h034.has_rule(DESC)
    assert not h034.has_rule("If the match is canceled, this market will resolve to 50-50.")
    assert h034.is_last_game_prop("Game 3: Ends in Daytime?", DESC, "Dota 2: A vs B (BO3) - X")
    assert not h034.is_last_game_prop("Game 3: Ends in Daytime?", DESC, "Dota 2: A vs B (BO5) - X")
    assert not h034.is_last_game_prop("Game 2: Ends in Daytime?", DESC, "Dota 2: A vs B (BO2) - X")


def test_decided_time_both_sides():
    s = [tr(100, 0.6), tr(200, 0.005, "SELL", 1), tr(300, 0.995)]
    assert h034.decided_time(s) == 200
    assert h034.decided_time([tr(1, 0.98), tr(2, 0.02)]) is None


def test_prop_ok():
    assert h034.prop_ok([tr(50, 0.5), tr(150, 0.995)], 100)
    assert not h034.prop_ok([tr(100, 0.01, k=1)], 100)   # en t_d también descalifica


def test_entries_hand():
    td, rate = 1000, 0.05
    P = [tr(td + 900, 0.10),                  # justo en t_d+15min: excluido (intervalo abierto)
         tr(td + 901, 0.48),                  # 0.48 + fee > 0.47: no
         tr(td + 902, 0.40, "SELL"),          # taker SELL: no
         tr(td + 903, 0.30, size=7),          # primera entrada YES
         tr(td + 904, 0.20),                  # segunda en YES: ignorada (máx 1 por token)
         tr(td + 905, 0.45, k=1, size=3),     # 0.45 + 0.05·0.45·0.55 = 0.462375 ≤ 0.47: sí
         tr(td + 6 * 3600 + 1, 0.10, k=1)]
    e = h034.entries(P, td, rate)
    assert [(x["outcome"], x["price"], x["size"]) for x in e] == [(0, 0.30, 7.0), (1, 0.45, 3.0)]
    # PnL a mano si se anula: 0.5 − 0.30 − 0.05·0.3·0.7 = 0.1895
    assert h034.pnl(0.30, rate, h034.payoff(0.5, 0)) == pytest.approx(0.1895)
    # Si no se anula y gana el outcome 1 (y=0): token 0 paga 0, token 1 paga 1
    assert h034.pnl(0.30, rate, h034.payoff(0.0, 0)) == pytest.approx(-0.3105)
    assert h034.pnl(0.45, rate, h034.payoff(0.0, 1)) == pytest.approx(1 - 0.462375)
    # costes x2: comisión doble + 0.01 de slippage
    assert h034.pnl(0.30, rate, 0.5, 2, 0.01) == pytest.approx(0.5 - 0.31 - 2 * 0.05 * 0.31 * 0.69)


def test_max_entry_price():
    p = h034.max_entry_price(0.05)
    assert p + h034.fee(p, 0.05) == pytest.approx(0.47, abs=1e-9)


def test_anti_lookahead_entries():
    """Alterar trades posteriores a la entrada (y el resultado) no cambia la decisión."""
    td = 1000
    P = [tr(td + 1000, 0.2), tr(td + 2000, 0.3, k=1), tr(td + 5000, 0.9)]
    e1 = h034.entries(P, td, 0.05)
    P2 = copy.deepcopy(P)
    P2[2]["price"] = 0.001
    P2.append(tr(td + 1500, 0.999, "SELL"))   # después de la entrada YES
    e2 = h034.entries(P2, td, 0.05)
    assert e1[0] == e2[0]
    # t_d solo depende de trades hasta t_d: añadir trades extremos posteriores no lo cambia
    S = [tr(10, 0.5), tr(td, 0.991)]
    assert h034.decided_time(S + [tr(td + 50, 0.999)]) == h034.decided_time(S) == td
    # prop_ok solo mira trades ≤ t_d
    assert h034.prop_ok(P2, td) == h034.prop_ok(P, td)


def test_fetch_full_splits():
    data = [{"timestamp": t} for t in range(0, 25000)]

    def fake(cid, a, b, cache):
        x = [d for d in data if a <= d["timestamp"] <= b]
        return sorted(x, key=lambda d: -d["timestamp"])[:10000]

    out = h034.fetch_full("c", 0, 24999, None, fetch=fake)
    assert sorted(d["timestamp"] for d in out) == list(range(25000))


def test_portfolio_return():
    # 1 USD de beneficio con 10 USD durante 1 día → 0.1·365
    assert h034.portfolio_return([1.0], [10.0], [1.0]) == pytest.approx(36.5)


def test_null_random_entries_lose_costs():
    """Comprar a 0.5 un token con pago 0/1 al azar pierde ≈ la comisión."""
    import numpy as np
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 200000)
    r = np.mean([h034.pnl(0.5, 0.05, v) for v in y])
    assert r == pytest.approx(-0.0125, abs=0.003)
