import numpy as np
import pandas as pd
import pytest
from math import erf, log, sqrt

from pmq import h005, h016


def test_parse_question():
    assert h016.parse_question("Will Bitcoin reach $114K before July 14?") == ("BTC", 114000.0, "up")
    assert h016.parse_question("Will Ethereum dip to $2,600 January 5-11?") == ("ETH", 2600.0, "down")
    assert h016.parse_question("Will $BTC reach 70k before September?") == ("BTC", 70000.0, "up")
    assert h016.parse_question("Will Ethereum hit $3,000.00 again by March 31?") == ("ETH", 3000.0, "up")
    assert h016.parse_question("Will Bitcoin ($BTC) hit $20,000 or less by June 30?") == ("BTC", 20000.0, "down")
    assert h016.parse_question("Will Ethereum hit $5000 by February 28 2025?") == ("ETH", 5000.0, "up")
    assert h016.parse_question("Will $ETH hit 3 digits (sub $1000) by June 30?") == ("ETH", 1000.0, "down")
    # dos barreras / sin importe / dos activos → fuera
    assert h016.parse_question("Will Bitcoin hit $73,000 or $74,000 first on March 16?") is None
    assert h016.parse_question("Will Bitcoin reach an all time high by May 30?") is None
    assert h016.parse_question("Will Bitcoin reach $100k before Ethereum reaches $5k?") is None


def test_desc_direction_y_fuente():
    assert h016.desc_direction('candle ... has a final "High" price equal to or greater') == "up"
    assert h016.desc_direction('has a final "Low" price of $2,000.00 or lower') == "down"
    assert h016.desc_direction('"High" and "Low" prices') is None
    assert h016.source("resolution source ... Binance BTC/USDT") == "binance"
    assert h016.source("as per Coingecko") == "coingecko"


def test_p_touch_a_mano():
    phi = lambda x: 0.5 * (1 + erf(x / sqrt(2)))
    S, X, s, tau = 100.0, 110.0, 0.001, 4320
    exp = 2 * phi(-log(1.1) / (0.001 * sqrt(4320)))
    assert h016.p_touch(S, X, s, tau) == pytest.approx(exp)
    # simétrica en log: barrera abajo a la misma distancia logarítmica
    assert h016.p_touch(S, S * S / X, s, tau) == pytest.approx(exp)
    assert h016.p_touch(100, 100, s, tau) == pytest.approx(1.0)
    # Monte Carlo grueso de un paseo gaussiano (reflexión ≈ continuo)
    rng = np.random.default_rng(0)
    paths = np.cumsum(rng.normal(0, 0.001, size=(4000, 2000)), axis=1)
    mc = (paths.max(1) >= log(1.05)).mean()
    assert h016.p_touch(100, 105, 0.001, 2000) == pytest.approx(mc, abs=0.03)


def _klines(t0, n, price_fn):
    idx = pd.date_range(t0, periods=n, freq="1min", tz="UTC")
    c = np.array([price_fn(i) for i in range(n)], float)
    return pd.DataFrame({"open": c, "high": c * 1.0005, "low": c * 0.9995, "close": c}, index=idx)


def _tr(i, px, ts, side="BUY"):
    return {"outcomeIndex": i, "side": side, "price": px, "timestamp": ts}


def _setup():
    end = pd.Timestamp("2025-01-20 04:00", tz="UTC")
    start = end - pd.Timedelta("12D")
    rng = np.random.default_rng(1)
    steps = rng.normal(0, 0.0008, 20 * 1440)
    k = _klines(start - pd.Timedelta("1D"), 20 * 1440, lambda i: 100 * np.exp(steps[: i + 1].sum()))
    return start, end, k


def test_evaluate_decision_a_mano_y_pnl():
    start, end, k = _setup()
    t = end - h016.LEAD
    S = k.loc[: t - pd.Timedelta(minutes=1)].close.iloc[-1]
    X = S * 1.30                                   # barrera muy lejana → P_toque ≈ 0
    ts = int(t.timestamp())
    trades = [_tr(0, 0.30, ts - 100), _tr(0, 0.20, ts - 50), _tr(1, 0.75, ts - 10), _tr(1, 0.10, ts + 10)]
    r = h016.evaluate(X, "up", start, end, None, k, trades, rate=0.0)
    assert r["why"] is None and r["fair"] < 0.01
    # peor compra NO en (t−1h, t] = 0.75 (el trade a 0.10 es posterior a t)
    assert r["side"] == "NO" and r["px"] == 0.75
    assert r["edge"] == pytest.approx(1 - r["fair"] - 0.75)
    assert h005.pnl("NO", 0.75, 0.0, 0.0) == pytest.approx(0.25)
    assert h005.pnl("NO", 0.75, 0.0, 1.0) == pytest.approx(-0.75)


def test_tocada_antes_de_t_y_filtros():
    start, end, k = _setup()
    t = end - h016.LEAD
    k2 = k.copy()
    k2.loc[start + pd.Timedelta("1D"), "high"] = 1e9           # toque antes de t
    ts = int(t.timestamp())
    trades = [_tr(0, 0.5, ts - 10), _tr(1, 0.5, ts - 10)]
    assert h016.evaluate(1e8, "up", start, end, None, k2, trades, 0.0)["why"] == "tocada_antes_de_t"
    k3 = k.copy()
    k3.loc[start + pd.Timedelta("1D"), "low"] = 1e-6
    assert h016.evaluate(1e-3, "down", start, end, None, k3, trades, 0.0)["why"] == "tocada_antes_de_t"
    # toque antes del inicio del mercado no cuenta
    k4 = k.copy()
    k4.loc[start - pd.Timedelta("1h"), "high"] = 1e9
    assert h016.evaluate(1e8, "up", start, end, None, k4, trades, 0.0)["why"] != "tocada_antes_de_t"
    assert h016.evaluate(1e8, "up", start, end, t - pd.Timedelta("1s"), k, trades, 0.0)["why"] == "cerrado_antes_de_t"
    assert h016.evaluate(1e8, "up", t + pd.Timedelta("1h"), end, None, k, trades, 0.0)["why"] == "no_abierto_en_t"
    assert h016.evaluate(1e8, "up", start, end, None, k, [], 0.0)["why"] == "sin_trades"


def test_anti_lookahead():
    """Cambiar klines y trades posteriores a t (incluido el toque/resultado) no cambia la decisión."""
    start, end, k = _setup()
    t = end - h016.LEAD
    S = k.loc[: t - pd.Timedelta(minutes=1)].close.iloc[-1]
    ts = int(t.timestamp())
    trades = [_tr(0, 0.40, ts - 300), _tr(1, 0.55, ts - 200)]
    for X, d in [(S * 1.02, "up"), (S * 0.97, "down"), (S * 1.3, "up")]:
        base = h016.evaluate(X, d, start, end, None, k, trades, 0.07)
        kf = k.copy()
        after = kf.index >= t                                         # vela que abre en t aún no ha cerrado
        kf.loc[after, ["open", "high", "low", "close"]] *= 5.0         # el futuro toca cualquier barrera
        kf.loc[t - pd.Timedelta(seconds=30): t, "high"] = kf.loc[t - pd.Timedelta(seconds=30): t, "high"]
        tf = trades + [_tr(0, 0.99, ts + 1), _tr(1, 0.01, ts + 5), _tr(0, 0.01, ts + 3600)]
        new = h016.evaluate(X, d, start, end, end + pd.Timedelta("1h"), kf, tf, 0.07)
        for key in ("why", "fair", "S", "sigma", "px_yes", "px_no", "side", "px", "edge"):
            a, b = base[key], new[key]
            if isinstance(a, float) and np.isnan(a):
                assert isinstance(b, float) and np.isnan(b)
            else:
                assert a == b, key


def test_nulo_precio_justo_no_opera():
    """Si el precio ejecutable coincide con la probabilidad del modelo, no hay señal (edge < θ)."""
    start, end, k = _setup()
    t = end - h016.LEAD
    S = k.loc[: t - pd.Timedelta(minutes=1)].close.iloc[-1]
    start = t - pd.Timedelta("2h")
    X = k.loc[start: t].high.max() * 1.002        # justo por encima del máximo desde el inicio → no tocada
    ts = int(t.timestamp())
    r0 = h016.evaluate(X, "up", start, end, None, k, [_tr(0, 0.5, ts - 1)], 0.0)
    f = r0["fair"]
    assert r0["why"] in (None, "sin_senal") and 0.05 < f < 0.99
    r = h016.evaluate(X, "up", start, end, None, k, [_tr(0, f, ts - 1), _tr(1, 1 - f, ts - 1)], 0.07)
    assert r["side"] is None and r["why"] == "sin_senal"


def test_touched_ventana():
    k = _klines("2025-01-01", 10, lambda i: 100.0)
    k.loc[pd.Timestamp("2025-01-01 00:05", tz="UTC"), "high"] = 120
    a = pd.Timestamp("2025-01-01", tz="UTC")
    assert h016.touched(k, 110, "up", a, a + pd.Timedelta(minutes=6))
    assert not h016.touched(k, 110, "up", a, a + pd.Timedelta(minutes=5))
    assert not h016.touched(k, 90, "down", a, a + pd.Timedelta(minutes=10))
