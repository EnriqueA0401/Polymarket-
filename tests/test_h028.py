import numpy as np
import pandas as pd
import pytest

from pmq import h028, h005

UTC = "UTC"


def _hist(dates, beats):
    return pd.DataFrame({"date": pd.to_datetime(dates, utc=True), "beat": beats})


def test_parse_ticker_and_strike_and_date():
    assert h028.parse_ticker("Will McCormick (MKC) beat quarterly earnings?") == "MKC"
    assert h028.parse_ticker("Will Broadcom beat Q2 earnings forecast ($1.57 EPS)?",
                             "reported by Broadcom Inc. (NASDAQ: AVGO) for") == "AVGO"
    assert h028.parse_strike("reports non-GAAP EPS greater than $2.05 for the") == 2.05
    assert h028.parse_strike("non-GAAP EPS greater than -$0.12 for") == -0.12
    assert h028.parse_strike("non-GAAP EPS greater than $-0.30 for") == -0.30
    d = h028.parse_est_date("is estimated to release earnings on October 9, 2026. The")
    assert (d.year, d.month, d.day) == (2026, 10, 9)


def test_beat_flag_tie_is_not_beat():
    assert h028.beat_flag(1.58, 1.57) == 1.0
    assert h028.beat_flag(1.57, 1.57) == 0.0
    assert h028.beat_flag(1.571, 1.574) == 0.0   # ambos redondean a 1.57
    assert np.isnan(h028.beat_flag(np.nan, 1.0))


def test_base_rate_hand():
    # 3 batidas de 4 → (3 + 0.76·4)/(4 + 4) = 6.04/8 = 0.755
    h = _hist(["2024-01-10", "2024-04-10", "2024-07-10", "2024-10-10"], [1, 1, 0, 1])
    p, n, k = h028.base_rate(h, pd.Timestamp("2025-01-01", tz=UTC))
    assert (n, k) == (4, 3) and p == pytest.approx(6.04 / 8)
    # sin historial → prior
    assert h028.base_rate(h.iloc[:0], pd.Timestamp("2025-01-01", tz=UTC)) == (0.76, 0, 0)


def test_base_rate_uses_last_8_and_skips_nan():
    dates = pd.date_range("2020-01-15", periods=12, freq="91D", tz=UTC)
    beats = [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, np.nan, 1]
    p, n, k = h028.base_rate(_hist(dates, beats), pd.Timestamp("2030-01-01", tz=UTC))
    # válidos: 11 (0..9, 11); últimos 8 → índices 3..9, 11 → beats 0,1,1,1,1,1,1,1 = 7
    assert (n, k) == (8, 7) and p == pytest.approx((7 + 3.04) / 12)


def test_anti_lookahead_reports_at_or_after_t_ignored():
    t = pd.Timestamp("2025-06-04 20:00", tz=UTC)
    past = _hist(["2024-06-01", "2024-09-01", "2024-12-01", "2025-03-01"], [1, 0, 1, 1])
    p0 = h028.base_rate(past, t)
    # añadir informes en t exacto y después (con resultados extremos) no cambia nada
    fut = pd.concat([past, _hist([t, t + pd.Timedelta("1s"), "2025-06-05 20:00", "2026-01-01"], [0, 0, 0, 0])])
    assert h028.base_rate(fut, t) == p0
    fut2 = pd.concat([past, _hist([t, "2025-06-05 20:00"], [1, 1])])
    assert h028.base_rate(fut2, t) == p0
    # un informe 1 segundo antes de t sí entra
    p1 = h028.base_rate(pd.concat([past, _hist([t - pd.Timedelta("1s")], [0])]), t)
    assert p1[1] == p0[1] + 1


def test_decision_time_and_match():
    rep = pd.Timestamp("2025-06-05 20:00", tz=UTC)
    assert h028.decision_time(rep, None) == pd.Timestamp("2025-06-04 20:00", tz=UTC)
    end = pd.Timestamp("2025-06-05 22:00", tz=UTC)
    assert h028.decision_time(pd.NaT, end) == pd.Timestamp("2025-06-04 22:00", tz=UTC)
    h = _hist(["2025-03-06 21:00", "2025-06-05 20:00", "2025-09-04 20:00"], [1, 1, 1])
    r = h028.match_report(h, pd.Timestamp("2025-06-03", tz=UTC))
    assert r["date"] == rep
    assert h028.match_report(h, pd.Timestamp("2025-07-20", tz=UTC)) is None


def test_signal_and_pnl_hand():
    # prob 0.80, YES a 0.60, comisión 0.07 → edge = 0.80 − 0.60 − 0.07·0.6·0.4 = 0.1832 ≥ 0.05 → YES
    side, px, e = h005.decide(0.80, 0.60, 0.45, 0.07, theta=h028.THETA)
    assert side == "YES" and e == pytest.approx(0.1832)
    assert h005.pnl("YES", 0.60, 0.07, 1.0) == pytest.approx(1 - 0.60 - 0.0168)
    assert h005.pnl("YES", 0.60, 0.07, 0.0) == pytest.approx(-0.6168)
    # NO: prob 0.50 → 1−p = 0.5; NO a 0.40 → edge 0.5 − 0.4 − 0.0168 = 0.0832
    side, px, e = h005.decide(0.50, 0.70, 0.40, 0.07, theta=h028.THETA)
    assert side == "NO" and px == 0.40
    # mercado a la tasa base → sin apuesta
    assert h005.decide(0.76, 0.74, 0.27, 0.07, theta=h028.THETA)[0] is None


def test_null_random_bets_lose_costs():
    # mercado bien calibrado: y ~ Bernoulli(precio); apostar al azar ≈ −comisión media
    rng = np.random.default_rng(0)
    p = rng.uniform(0.2, 0.8, 200000)
    y = (rng.uniform(size=p.size) < p).astype(float)
    side = np.where(rng.uniform(size=p.size) < 0.5, "YES", "NO")
    px = np.where(side == "YES", p, 1 - p)
    pn = np.array([h005.pnl(s, q, 0.07, yy) for s, q, yy in zip(side, px, y)])
    expected = -(0.07 * px * (1 - px)).mean()
    assert pn.mean() == pytest.approx(expected, abs=0.004)
