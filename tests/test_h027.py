import math
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from pmq import h004, h027

NY = ZoneInfo("America/New_York")
D = date(2026, 3, 2)  # sin cambio de hora (EST, UTC−5)


def _obs(tz, target, hours_vals):
    """Observaciones a las HH:51 locales con los valores dados {hora local: valor}."""
    ts, v = [], []
    for h, x in sorted(hours_vals.items()):
        ts.append(int(datetime(target.year, target.month, target.day, h, 51, tzinfo=tz).timestamp()))
        v.append(x)
    return np.array(ts), np.array(v)


def test_to_unit_redondeo():
    assert h027.to_unit(46.0, "F") == 46
    assert h027.to_unit(45.5, "F") == 46
    assert h027.to_unit(46.40, "C") == 8          # 8 °C exacto desde METAR entero
    assert h027.to_unit(26.6, "C") == -3          # M03
    assert h027.to_unit(32.0, "C") == 0


def test_bucket_ints():
    assert h027.bucket_ints("exact", 20.0, 20.0) == (20, 20)
    assert h027.bucket_ints("range", 62.0, 63.0) == (62, 63)
    assert h027.bucket_ints("ge", 23.0, math.inf) == (23, math.inf)
    assert h027.bucket_ints("le", -math.inf, 32.0) == (-math.inf, 32)


def test_tiempos_locales():
    t = h027.decision_ts(NY, D)
    assert t == int(datetime(2026, 3, 2, 20, 0, tzinfo=timezone.utc).timestamp())   # 15:00 EST = 20:00 UTC
    a, b = h027.local_day(NY, D)
    assert a == int(datetime(2026, 3, 2, 5, tzinfo=timezone.utc).timestamp()) and b - a == 86400


def test_nowcast_y_maximo_final_a_mano():
    vals = {h: 40 + h for h in range(0, 24)}          # sube 1 °F por hora; 14:51 → 54, 23:51 → 63
    vals.update({h: 50 for h in range(16, 24)})        # por la tarde baja: máximo final = 55 (15:51)
    ts, v = _obs(NY, D, vals)
    t, M = h027.nowcast_state(ts, v, NY, D)
    # corte = 14:45 local → la observación de 14:51 NO cuenta; la de 13:51 (=53) sí
    assert M == 53
    assert h027.final_max(ts, v, NY, D) == 55


def test_anti_lookahead():
    """Alterar observaciones posteriores a t − 15 min no cambia M, la probabilidad ni la decisión."""
    rng = np.random.default_rng(0)
    vals = {h: 40 + h for h in range(0, 24)}
    ts, v = _obs(NY, D, vals)
    # añadir observaciones en el borde: 14:44 (cuenta), 14:46 (no cuenta)
    e1 = int(datetime(2026, 3, 2, 14, 44, tzinfo=NY).timestamp())
    e2 = int(datetime(2026, 3, 2, 14, 46, tzinfo=NY).timestamp())
    ts = np.append(ts, [e1, e2]); v = np.append(v, [60, 99])
    t, M = h027.nowcast_state(ts, v, NY, D)
    assert M == 60
    dist = {0: 0.5, 1: 0.3, 3: 0.2}
    p = h027.bucket_prob(M, dist, 61, 62)
    dec = h027.decide(p, 0.10, 0.92, 0.05)
    cut = t - h027.INFO_LAG_S
    for _ in range(20):
        v2 = v.copy()
        late = ts > cut
        v2[late] = rng.integers(-50, 150, late.sum())
        t2, M2 = h027.nowcast_state(ts, v2, NY, D)
        assert M2 == M
        assert h027.decide(h027.bucket_prob(M2, dist, 61, 62), 0.10, 0.92, 0.05) == dec
    # un dato anterior al corte sí cambia M (el test detecta dependencia)
    v3 = v.copy(); v3[ts == e1] = 70
    assert h027.nowcast_state(ts, v3, NY, D)[1] == 70


def test_calidad_minima():
    ts, v = _obs(NY, D, {h: 50 for h in range(0, 5)})           # solo madrugada
    assert h027.nowcast_state(ts, v, NY, D)[1] is None
    ts, v = _obs(NY, D, {h: 50 for h in range(0, 10)})          # 10 horas pero nada en las 2 h previas
    assert h027.nowcast_state(ts, v, NY, D)[1] is None
    ts, v = _obs(NY, D, {h: 50 for h in range(0, 12)})          # falta la tarde → sin máximo final
    assert h027.final_max(ts, v, NY, D) is None


def test_distribucion_y_prob_a_mano():
    dist = h027.fit_rise([0, 0, 0, 1, 1, 2, 0, 0, 1, 3])
    assert dist == {0: 0.5, 1: 0.3, 2: 0.1, 3: 0.1}
    M = 20
    assert h027.bucket_prob(M, dist, 20, 20) == pytest.approx(0.5)
    assert h027.bucket_prob(M, dist, 21, 22) == pytest.approx(0.4)
    assert h027.bucket_prob(M, dist, 23, math.inf) == pytest.approx(0.1)
    assert h027.bucket_prob(M, dist, -math.inf, 19) == 0.0          # tramo muerto
    # partición completa suma 1
    s = sum(h027.bucket_prob(M, dist, a, b) for a, b in [(-math.inf, 19), (20, 20), (21, 21), (22, 22), (23, math.inf)])
    assert s == pytest.approx(1.0)


def test_decision_y_pnl_a_mano():
    # tramo muerto (prob 0); NO a 0.80 con comisión 0.05: edge = 1 − 0.80 − 0.05·0.8·0.2 = 0.192
    side, px, edge = h027.decide(0.0, 0.25, 0.80, 0.05)
    assert side == "NO" and px == 0.80 and edge == pytest.approx(0.192)
    assert h004.pnl(1, 0.80, 0.05, 0.0) == pytest.approx(0.192)     # gana NO
    assert h004.pnl(1, 0.80, 0.05, 1.0) == pytest.approx(-0.808)    # pierde NO
    assert h027.decide(0.5, 0.48, 0.50, 0.05)[0] is None             # edge < 0.05


def test_rentabilidades_cartera():
    # dos apuestas: capital 1 durante 1 día y 1 durante 1 día, pnl total 0.02 → 0.02/2·365
    assert h027.portfolio_return([0.01, 0.01], [1, 1], [1, 1]) == pytest.approx(3.65)
    d = 86400
    r, peak = h027.bankroll_return([0.01, 0.01], [1.0, 1.0], [0, 0], [d, d])
    assert peak == 2.0 and r == pytest.approx(0.02 / 2 / (1 / 365))
    r, peak = h027.bankroll_return([0.01, 0.01], [1.0, 1.0], [0, d], [d, 2 * d])     # secuenciales
    assert peak == 1.0 and r == pytest.approx(0.02 / 1 / (2 / 365))
