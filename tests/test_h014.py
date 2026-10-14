import math
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from scipy.stats import norm

from pmq import h014


def test_parse_variantes():
    p = h014.parse_question("Will the highest temperature in Kuala Lumpur be 32°C on October 14?")
    assert p == {"city": "Kuala Lumpur", "unit": "C", "kind": "exact", "lo": 32.0, "hi": 32.0, "month": 10, "day": 14}
    p = h014.parse_question("Will the highest temperature in NYC be between 62-63°F on May 21?")
    assert p["city"] == "New York City" and p["kind"] == "range" and (p["lo"], p["hi"]) == (62, 63)
    p = h014.parse_question("Will the highest temperature in New York City be between -5--4°F on February 2?")
    assert (p["lo"], p["hi"]) == (-5, -4)
    p = h014.parse_question("Will the highest temperature in Moscow be -3°C or below on March 1?")
    assert p["kind"] == "le" and p["hi"] == -3 and p["lo"] == -math.inf
    p = h014.parse_question("Will the highest temperature in Paris be 23°C or higher on April 19?")
    assert p["kind"] == "ge" and p["lo"] == 23 and p["hi"] == math.inf
    p = h014.parse_question("Will the highest temperature in NYC 36°F or below on January 26?")
    assert p["city"] == "New York City" and p["kind"] == "le"
    p = h014.parse_question("Will the highest temperature in NYC be be tween 70-71°F on May 4?")
    assert p["kind"] == "range" and p["city"] == "New York City"
    assert h014.parse_question("Will it rain in London on May 4?") is None


def test_intervalos_a_mano():
    assert h014.interval_c({"lo": 32, "hi": 32, "unit": "C"}) == (31.5, 32.5)
    a, b = h014.interval_c({"lo": 50, "hi": 51, "unit": "F"})
    assert a == pytest.approx((49.5 - 32) * 5 / 9) and b == pytest.approx((51.5 - 32) * 5 / 9)
    assert h014.interval_c({"lo": 23, "hi": math.inf, "unit": "C"}) == (22.5, math.inf)
    assert h014.interval_c({"lo": -math.inf, "hi": 20, "unit": "C"}) == (-math.inf, 20.5)


def test_bucket_prob_a_mano_y_particion():
    # pronóstico 20, sesgo +1, sd 1 → T~N(21,1); tramo 21 → P(20.5≤T<21.5) = 2Φ(.5)−1
    assert h014.bucket_prob(20, 1, 1, 20.5, 21.5) == pytest.approx(2 * norm.cdf(0.5) - 1)
    edges = [-math.inf, 18.5, 19.5, 20.5, 21.5, 22.5, math.inf]
    s = sum(h014.bucket_prob(20, 1, 1.3, a, b) for a, b in zip(edges[:-1], edges[1:]))
    assert s == pytest.approx(1.0)


def test_fit_error_recupera_parametros():
    rng = np.random.default_rng(0)
    e = rng.normal(0.7, 1.5, 4000)
    k = np.round(e)                                   # observado redondeado al entero
    lo, hi = k - 0.5, k + 0.5
    lo = np.where(k >= 3, 2.5, lo); hi = np.where(k >= 3, np.inf, hi)   # tramo abierto "≥3"
    mu, sd = h014.fit_error(lo, hi)
    assert mu == pytest.approx(0.7, abs=0.07) and sd == pytest.approx(1.5, abs=0.07)


def test_decide_y_pnl_a_mano():
    s, px, e = h014.decide(0.60, 0.50, 0.55, 0.0)
    assert s == "YES" and e == pytest.approx(0.10)
    assert h014.pnl("YES", 0.50, 0.0, 1.0) == pytest.approx(0.50)
    assert h014.pnl("YES", 0.50, 0.0, 0.0) == pytest.approx(-0.50)
    s, px, e = h014.decide(0.10, 0.30, 0.70, 0.05)
    assert s == "NO" and e == pytest.approx(0.90 - 0.70 - 0.05 * 0.7 * 0.3)
    assert h014.pnl("NO", 0.70, 0.05, 0.0) == pytest.approx(0.30 - 0.05 * 0.21)
    assert h014.decide(0.53, 0.50, None, 0.0)[0] is None       # edge 0.03 < 0.05
    assert h014.decide(0.53, None, None, 0.0)[0] is None
    # costes ×2: comisión doble y precio + deslizamiento
    assert h014.pnl("YES", 0.50, 0.05, 1.0, 2.0, 0.01) == pytest.approx(1 - 0.51 - 2 * 0.05 * 0.51 * 0.49)


def test_tiempos_y_leads():
    t = h014.decision_time(date(2026, 3, 15))
    assert t == int(datetime(2026, 3, 14, 12, tzinfo=timezone.utc).timestamp())
    h = int(datetime(2026, 3, 15, 6, tzinfo=timezone.utc).timestamp())
    assert h014.lead_for_hour(h, t) == 1                  # emitido 14/03 06:00, publicado 12:00 ≤ t
    assert h014.lead_for_hour(h + 3600, t) == 2           # previous_day1 se publicaría después de t
    assert h014.lead_for_hour(h + 86400 + 3600, t) == 3
    L = h014.leads_used(ZoneInfo("Europe/London"), date(2026, 3, 15), t)
    assert len(L) == 24 and L[:7] == [1] * 7 and L[7:] == [2] * 17
    assert len(h014.leads_used(ZoneInfo("Europe/London"), date(2026, 3, 29), t + 14 * 86400)) == 23   # cambio de hora


def _hourly(tz, target, f):
    out = {}
    start = int(datetime(target.year, target.month, target.day, tzinfo=tz).astimezone(timezone.utc).timestamp())
    for i in range(-30, 60):
        ts = start + 3600 * i
        out[ts] = {k: f(ts, k) for k in (1, 2, 3)}
    return out


def test_daily_max_usa_lead_correcto():
    tz = ZoneInfo("Europe/London")
    tg = date(2026, 3, 15)
    t = h014.decision_time(tg)
    # lead1 = 30, lead2 = 20, lead3 = 10 en todas las horas → el máximo debe ser 30 (horas tempranas usan lead1)
    hd = _hourly(tz, tg, lambda ts, k: {1: 30.0, 2: 20.0, 3: 10.0}[k])
    assert h014.daily_max_forecast(hd, tz, tg, t) == 30.0
    # si solo las horas tardías (lead2) son altas
    hd = _hourly(tz, tg, lambda ts, k: 25.0 if k == 2 else 5.0)
    assert h014.daily_max_forecast(hd, tz, tg, t) == 25.0
    del hd[min(hd) + 30 * 3600]                            # falta una hora del día → None
    assert h014.daily_max_forecast(hd, tz, tg, t) is None


def test_anti_lookahead():
    """Alterar pronósticos emitidos después de t y trades posteriores a t no cambia la decisión en t."""
    from pmq import h005
    tz = ZoneInfo("America/New_York")
    tg = date(2026, 3, 15)
    t = h014.decision_time(tg)
    base = lambda ts, k: 15.0 + (ts % 86400) / 86400 * 5 - k
    hd = _hourly(tz, tg, base)
    f0 = h014.daily_max_forecast(hd, tz, tg, t)
    # corromper toda predicción cuya emisión + LAG > t (emisión = hora − 24k h)
    hd2 = {ts: {k: (99.0 if ts - 86400 * k + 3600 * h014.LAG_H > t else v) for k, v in row.items()} for ts, row in hd.items()}
    assert h014.daily_max_forecast(hd2, tz, tg, t) == f0
    tr = [{"outcomeIndex": 0, "side": "BUY", "price": 0.30, "timestamp": t - 100},
          {"outcomeIndex": 1, "side": "BUY", "price": 0.72, "timestamp": t - 50}]
    tr2 = tr + [{"outcomeIndex": 0, "side": "BUY", "price": 0.99, "timestamp": t + 1},
                {"outcomeIndex": 1, "side": "BUY", "price": 0.01, "timestamp": t + 60}]
    p = h014.bucket_prob(f0, 0.0, 1.5, 17.5, 18.5)
    d1 = h014.decide(p, h005.exec_price(tr, 0, t - 3600, t), h005.exec_price(tr, 1, t - 3600, t), 0.05)
    d2 = h014.decide(p, h005.exec_price(tr2, 0, t - 3600, t), h005.exec_price(tr2, 1, t - 3600, t), 0.05)
    assert d1[0] == d2[0] and (d1[1] == d2[1] or (np.isnan(d1[1]) and np.isnan(d2[1])))
    # con un sesgo que sí genera señal, la decisión tampoco cambia
    p2 = h014.bucket_prob(f0, 0.0, 0.5, f0 - 0.5, f0 + 0.5)
    d1 = h014.decide(p2, h005.exec_price(tr, 0, t - 3600, t), h005.exec_price(tr, 1, t - 3600, t), 0.05)
    d2 = h014.decide(p2, h005.exec_price(tr2, 0, t - 3600, t), h005.exec_price(tr2, 1, t - 3600, t), 0.05)
    assert d1[0] == "YES" and d1[:2] == d2[:2]


def test_nulo_aleatorio_da_menos_costes():
    """Si el precio es la probabilidad verdadera, comprar al azar pierde ≈ la comisión."""
    rng = np.random.default_rng(1)
    n = 200000
    p = rng.uniform(0.05, 0.95, n)
    y = (rng.uniform(size=n) < p).astype(float)
    side = rng.choice(["YES", "NO"], n)
    px = np.where(side == "YES", p, 1 - p)
    r = 0.05
    pn = np.array([h014.pnl(s, q, r, yy) for s, q, yy in zip(side, px, y)])
    assert pn.mean() == pytest.approx(-np.mean(r * px * (1 - px)), abs=0.004)


def test_estacion_y_fecha():
    d = "recorded at ... https://www.wunderground.com/history/daily/gb/london/EGLC. To toggle"
    assert h014.station_from_description(d) == "EGLC"
    assert h014.station_from_description("see https://www.wunderground.com/weather/KORD now") == "KORD"
    assert h014.station_from_description("https://www.weather.gov/wrh/timeseries?site=zgsz\n") == "ZGSZ"
    assert h014.station_from_description("recorded by the Hong Kong Observatory in") == "HKO"
    import pandas as pd
    assert h014.target_date(1, 2, pd.Timestamp("2026-01-02T12:00Z")) == date(2026, 1, 2)
    assert h014.target_date(12, 31, pd.Timestamp("2026-01-01T12:00Z")) == date(2025, 12, 31)
