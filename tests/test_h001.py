import numpy as np
import pandas as pd
import pytest

from pmq import h001

T0 = pd.Timestamp("2025-01-10", tz="UTC")


def uni(rows):
    base = dict(start=T0 - pd.Timedelta("30d"), closed_time=T0 + pd.Timedelta("1h"),
                category="x", fee_schedule=None, volume=1.0, clean=True)
    return pd.DataFrame([{**base, **r} for r in rows])


def test_pnl_a_mano():
    u = uni([dict(id=1, event_id="a", end=T0, y=1.0), dict(id=2, event_id="b", end=T0, y=1.0)])
    t = (T0 - pd.Timedelta("24h")).timestamp()
    hist = {1: [{"t": t - 60, "p": 0.95}], 2: [{"t": t - 60, "p": 0.05}]}
    obs = h001.observations(u, hist, pd.Timedelta("24h"))
    tr = h001.trades(obs).set_index("id")
    # mercado 1: compra YES a 0.95+0.02=0.97, fee 0.07*0.97*0.03
    q = 0.97; fee = 0.07 * q * (1 - q)
    assert tr.loc[1, "ret"] == pytest.approx((1 - q - fee) / (q + fee))
    # mercado 2: compra NO a 0.97, NO paga 0 porque y=1
    assert tr.loc[2, "ret"] == pytest.approx(-1.0)


def test_anti_lookahead():
    u = uni([dict(id=1, event_id="a", end=T0, y=1.0)])
    t = (T0 - pd.Timedelta("24h")).timestamp()
    h1 = {1: [{"t": t - 60, "p": 0.93}, {"t": t + 60, "p": 0.99}]}
    h2 = {1: [{"t": t - 60, "p": 0.93}, {"t": t + 60, "p": 0.01}]}
    u2 = u.copy(); u2["y"] = 0.0
    a = h001.observations(u, h1, pd.Timedelta("24h"))
    b = h001.observations(u2, h2, pd.Timedelta("24h"))
    assert a.p.tolist() == b.p.tolist() == [0.93]
    assert h001.trades(a).side.tolist() == h001.trades(b).side.tolist()


def test_mercado_cerrado_antes_de_t_excluido():
    u = uni([dict(id=1, event_id="a", end=T0, y=1.0, closed_time=T0 - pd.Timedelta("2d"))])
    t = (T0 - pd.Timedelta("24h")).timestamp()
    obs = h001.observations(u, {1: [{"t": t - 60, "p": 0.95}]}, pd.Timedelta("24h"))
    assert obs.empty


def test_precio_viejo_descartado():
    u = uni([dict(id=1, event_id="a", end=T0, y=1.0)])
    t = (T0 - pd.Timedelta("24h")).timestamp()
    obs = h001.observations(u, {1: [{"t": t - 7 * 3600, "p": 0.95}]}, pd.Timedelta("24h"))
    assert obs.empty


def test_nulo_aleatorio_da_menos_costes():
    # mercados perfectamente calibrados: y ~ Bernoulli(p). Retorno medio ≈ -costes.
    rng = np.random.default_rng(1)
    n = 200_000
    p = rng.choice([0.03, 0.05, 0.08, 0.92, 0.95, 0.97], n)
    y = (rng.random(n) < p).astype(float)
    obs = pd.DataFrame(dict(id=range(n), event_id=range(n), t=T0, close=T0 + pd.Timedelta("1d"),
                            p=p, y=y, clean=True, category="x", fee_rate=0.07, volume=1.0))
    tr = h001.trades(obs)
    tok = np.where(tr.side == "YES", tr.p, 1 - tr.p)
    expected = ((tok - tr.q - tr.fee) / (tr.q + tr.fee)).mean()
    assert tr.ret.mean() == pytest.approx(expected, abs=0.003)
    assert tr.ret.mean() < 0


def test_bootstrap_cubre_media():
    df = pd.DataFrame({"ret": np.r_[np.ones(50), -np.ones(50)] * 0.1, "event_id": np.arange(100)})
    lo, hi = h001.cluster_bootstrap(df)
    assert lo < 0 < hi
