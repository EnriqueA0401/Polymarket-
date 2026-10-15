"""Tests H042: comisión ceil, inversión YES/NO de libros Kalshi, barrido de profundidad, NaN sin profundidad,
cobertura de cubos, Σ YES / Σ NO y dirección de escaleras (cuentas a mano)."""
import numpy as np
import pandas as pd
import pytest

from pmq import h042 as K

TS = pd.Timestamp("2030-01-01", tz="UTC")
CLOSE = "2030-01-11T00:00:00Z"          # 10 días


def bk(yes_ask=None, no_ask=None, size=1000):
    """Libro Kalshi (solo bids): ask YES a p ≡ bid NO a 1−p; ask NO a q ≡ bid YES a 1−q."""
    return {"no_dollars": [[f"{1 - yes_ask:.4f}", str(size)]] if yes_ask is not None else [],
            "yes_dollars": [[f"{1 - no_ask:.4f}", str(size)]] if no_ask is not None else []}


def mk(t, st="between", fl=None, cap=None, rules="If X is between # and #, Yes.", close=CLOSE, status="active"):
    return {"ticker": t, "strike_type": st, "floor_strike": fl, "cap_strike": cap, "rules_primary": rules,
            "close_time": close, "status": status}


def test_fee_ceil():
    assert K.k_fee(0.40, 10) == pytest.approx(0.17)      # 0.168 → 0.17
    assert K.k_fee(0.50, 10) == pytest.approx(0.18)      # 0.175 → 0.18
    assert K.k_fee(0.62, 10) == pytest.approx(0.17)      # 0.16492 → 0.17
    assert K.k_fee(0.01, 10) == pytest.approx(0.01)      # 0.00693 → 0.01


def test_yes_no_inversion():
    b = {"no_dollars": [["0.60", "100"]], "yes_dollars": [["0.35", "100"]]}
    assert K.best_ask(b, "yes") == pytest.approx(0.40)
    assert K.best_ask(b, "no") == pytest.approx(0.65)
    assert K.leg_cost(b, "yes") == pytest.approx(4.00 + 0.17)
    assert K.leg_cost(b, "no") == pytest.approx(6.50 + 0.16)   # 0.07·10·0.65·0.35 = 0.15925 → 0.16


def test_depth_sweep_and_nan():
    b = {"no_dollars": [["0.60", "4"], ["0.55", "100"]], "yes_dollars": []}
    # 4 @ 0.40 (+0.0672→0.07) + 6 @ 0.45 (+0.10395→0.11)
    assert K.leg_cost(b, "yes") == pytest.approx(1.60 + 0.07 + 2.70 + 0.11)
    assert np.isnan(K.leg_cost(b, "no"))                          # lado vacío
    assert np.isnan(K.leg_cost({"no_dollars": [["0.60", "5"]]}, "yes"))   # 5 < 10
    assert np.isnan(K.leg_cost(None, "yes"))


def test_coverage():
    ok = [mk("L", "less", cap=74), mk("B1", fl=74, cap=75), mk("B2", fl=76, cap=77), mk("H", "greater", fl=77)]
    assert K.coverage(ok) == (True, "ok")
    assert K.coverage(ok[:3])[0] is False                                   # sin cola superior
    gap = [mk("L", "less", cap=74), mk("B1", fl=74, cap=75), mk("B2", fl=77, cap=78), mk("H", "greater", fl=78)]
    assert K.coverage(gap)[0] is False                                      # hueco 2 (76 sin cubo) ≠ paso 1
    gap2 = gap + [mk("B3", fl=80, cap=81)]
    assert K.coverage(gap2)[0] is False
    hi_gap = [mk("L", "less", cap=74), mk("B1", fl=74, cap=75), mk("H", "greater", fl=76)]
    assert K.coverage(hi_gap)[0] is False                                   # 76 sin cubo (>76 lo excluye)
    hi_ge = [mk("L", "less", cap=74), mk("B1", fl=74, cap=75), mk("B2", fl=76, cap=77), mk("H", "greater_or_equal", fl=78)]
    assert K.coverage(hi_ge) == (True, "ok")                                # ≥78 tras 77, paso 1
    gdp = [mk("L", "less", cap=0.1), mk("B1", fl=0.1, cap=0.5), mk("B2", fl=0.6, cap=1.0), mk("H", "greater", fl=1.0)]
    assert K.coverage(gdp) == (True, "ok")
    cust = [mk("A", "custom"), mk("B", "custom")]
    assert K.coverage(cust) == (False, "no_numerico")
    over = [mk("L", "less", cap=74), mk("B1", fl=74, cap=76), mk("B2", fl=75, cap=77), mk("H", "greater", fl=77)]
    assert K.coverage(over) == (False, "solapamiento")


def test_me_yes_and_no():
    ms = [mk("L", "less", cap=10), mk("B", fl=10, cap=19), mk("H", "greater", fl=19)]
    ev = {"event_ticker": "E", "mutually_exclusive": True, "markets": ms}
    book = {t: bk(yes_ask=0.30, no_ask=0.62) for t in ("L", "B", "H")}
    rows = {r["kind"]: r for r in K.mutually_exclusive(ev, book, TS)}
    y, n = rows["me_yes"], rows["me_no"]
    assert y["cost"] == pytest.approx(3 * (3.00 + 0.15))                    # 0.147 → 0.15
    assert y["profit"] == pytest.approx(10 - 9.45)
    assert y["days"] == pytest.approx(10)
    assert y["ann"] == pytest.approx((0.55 / 9.45) * 36.5)
    assert y["opp"] is True
    assert n["cost"] == pytest.approx(3 * (6.20 + 0.17))
    assert n["payout"] == 20 and n["profit"] == pytest.approx(20 - 19.11)
    # cobertura no verificable → solo Σ NO
    ev2 = dict(ev, markets=ms[:2])
    kinds = [r["kind"] for r in K.mutually_exclusive(ev2, book, TS)]
    assert kinds == ["me_no"]
    # un mercado ya liquidado en YES excluido de los activos → Σ YES no válido
    ev3 = dict(ev, markets=ms + [mk("X", fl=20, cap=20, status="finalized") | {"result": "yes"}])
    assert [r["kind"] for r in K.mutually_exclusive(ev3, book, TS)] == ["me_no"]
    # libro vacío en una pata → NaN, sin oportunidad
    book2 = dict(book, B={"no_dollars": [], "yes_dollars": []})
    r = {r["kind"]: r for r in K.mutually_exclusive(ev, book2, TS)}
    assert np.isnan(r["me_yes"]["cost"]) and r["me_yes"]["opp"] is False
    # no excluyente → nada
    assert K.mutually_exclusive(dict(ev, mutually_exclusive=False), book, TS) == []


def test_ladder_direction_above():
    r_ = "If X is above #, Yes."
    ms = [mk("K200", "greater", fl=200, rules=r_), mk("K100", "greater", fl=100, rules=r_)]
    ev = {"event_ticker": "E", "mutually_exclusive": False, "markets": ms}
    # dirección correcta: YES(>100) a 0.40 + NO(>200) a 0.55; la invertida costaría 0.99 + 0.99
    book = {"K100": bk(yes_ask=0.40, no_ask=0.99), "K200": bk(yes_ask=0.99, no_ask=0.55)}
    (r,) = K.ladder_pairs(ev, book, TS)
    assert r["legs"] == "K100:yes|K200:no"
    assert r["cost"] == pytest.approx(4.00 + 0.17 + 5.50 + 0.18)            # 0.17325 → 0.18
    assert r["profit"] == pytest.approx(10 - 9.85)
    assert r["opp"] is True                                                  # 1.52 % y 55 % anualizado


def test_ladder_direction_below_and_filters():
    r_ = "If X is below #, Yes."
    ms = [mk("K100", "less", cap=100, rules=r_), mk("K200", "less", cap=200, rules=r_)]
    ev = {"event_ticker": "E", "mutually_exclusive": False, "markets": ms}
    book = {"K100": bk(yes_ask=0.99, no_ask=0.50), "K200": bk(yes_ask=0.45, no_ask=0.99)}
    (r,) = K.ladder_pairs(ev, book, TS)
    assert r["legs"] == "K200:yes|K100:no"                                   # {x<200} ⊇ {x<100}
    assert r["cost"] == pytest.approx(4.50 + 0.18 + 5.00 + 0.18)
    # fechas o plantillas distintas, o tipos mezclados → sin pareja
    assert K.ladder_pairs(dict(ev, markets=[ms[0], dict(ms[1], close_time="2031-01-01T00:00:00Z")]), book, TS) == []
    assert K.ladder_pairs(dict(ev, markets=[ms[0], dict(ms[1], rules_primary="If Y is below #, Yes.")]), book, TS) == []
    assert K.ladder_pairs(dict(ev, markets=[ms[0], dict(ms[1], strike_type="greater", floor_strike=200)]), book, TS) == []
    assert K.ladder_pairs(dict(ev, mutually_exclusive=True), book, TS) == []


def test_template_numbers():
    a = {"rules_primary": "If Henry records at least 14,000 yards before 2030, Yes."}
    b = {"rules_primary": "If Henry records at least 18,356 yards before 2030, Yes."}
    assert K._template(a) == K._template(b)


def test_chunks_keep_events_together():
    evs = [{"markets": [{"ticker": f"{i}-{j}", "status": "active"} for j in range(40)]} for i in range(5)]
    ch = K._chunks(evs)
    assert all(len(c) <= 100 for c in ch)
    for c in ch:
        assert len({t.split("-")[0] for t in c}) * 40 == len(c)              # eventos enteros
    big = [{"markets": [{"ticker": f"b-{j}", "status": "active"} for j in range(250)]}]
    assert [len(c) for c in K._chunks(big)] == [100, 100, 50]


def test_null_random_books_no_profit():
    """Test nulo: libros coherentes (asks ≥ prob. justa) nunca dan beneficio."""
    rng = np.random.default_rng(0)
    for _ in range(200):
        p = rng.dirichlet(np.ones(4))
        ms = [mk("L", "less", cap=0), mk("B1", fl=0, cap=1), mk("B2", fl=2, cap=3), mk("H", "greater", fl=3)]
        book = {m["ticker"]: bk(yes_ask=min(0.99, round(q + 0.01, 2)), no_ask=min(0.99, round(1 - q + 0.01, 2)))
                for m, q in zip(ms, p)}
        for r in K.mutually_exclusive({"event_ticker": "E", "mutually_exclusive": True, "markets": ms}, book, TS):
            assert not (r["profit"] > 0)
