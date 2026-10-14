import numpy as np
import pandas as pd
import pytest

from pmq import h004, h020

A0 = 1_000_000


def T(ts, p, idx=0, side="BUY", size=1.0):
    return {"timestamp": ts, "price": p, "outcomeIndex": idx, "side": side, "size": size}


def base():
    """Primer trade YES a 0.40; VWAP de [a0+50m, a0+60m] = (0.50*1 + 0.47*3)/4 = 0.4775 → deriva +0.0775."""
    return [T(A0, 0.40), T(A0 + 100, 0.65, idx=1),
            T(A0 + 2999, 0.99),                       # fuera de la ventana de VWAP (justo antes)
            T(A0 + 3000, 0.50, size=1), T(A0 + 3600, 0.47, side="SELL", size=3),
            T(A0 + 3600, 0.52, idx=1, size=5)]        # token NO: no entra en la VWAP YES


def test_signal_a_mano():
    d, p0, v, dr = h020.signal(base(), A0)
    assert p0 == pytest.approx(0.40)
    assert v == pytest.approx(0.4775)
    assert dr == pytest.approx(0.0775)
    assert d == 1
    assert h020.side(d, "A") == 0 and h020.side(d, "B") == 1
    assert h020.side(-1, "A") == 1 and h020.side(-1, "B") == 0


def test_umbral_y_zona():
    # deriva exactamente 0.05 → señal; 0.049 → no
    assert h020.signal([T(A0, 0.30), T(A0 + 3300, 0.35)], A0)[0] == 1
    assert h020.signal([T(A0, 0.30), T(A0 + 3300, 0.349)], A0)[0] == 0
    # a la baja
    assert h020.signal([T(A0, 0.60), T(A0 + 3300, 0.50)], A0)[0] == -1
    # VWAP fuera de [0.10, 0.90] → sin señal
    assert h020.signal([T(A0, 0.80), T(A0 + 3300, 0.91)], A0)[0] == 0
    assert h020.signal([T(A0, 0.80), T(A0 + 3300, 0.90)], A0)[0] == 1
    # sin trades YES en la ventana → sin señal
    assert h020.signal([T(A0, 0.30), T(A0 + 2000, 0.60)], A0)[0] == 0


def test_p0_primer_segundo_vwap_y_primer_trade_no():
    # el primer trade es de NO; el primer YES llega después y en el mismo segundo hay dos trades
    tr = [T(A0, 0.7, idx=1), T(A0 + 10, 0.20, size=1), T(A0 + 10, 0.40, size=3), T(A0 + 20, 0.9),
          T(A0 + 3100, 0.50)]
    d, p0, v, dr = h020.signal(tr, A0)
    assert p0 == pytest.approx(0.35) and v == pytest.approx(0.50) and d == 1


def test_anti_lookahead():
    """Cambiar trades posteriores a a0+60min (y el resultado) no altera la señal."""
    s0 = h020.signal(base(), A0)
    alt = base() + [T(A0 + 3601, 0.01, size=1e6), T(A0 + 5000, 0.99, idx=1, size=1e6), T(A0 + 10**6, 0.0)]
    assert h020.signal(alt, A0) == s0
    alt2 = [dict(x, price=0.95) if x["timestamp"] > A0 + 3600 else x for x in alt]
    assert h020.signal(alt2, A0) == s0
    # la entrada no usa nada en o antes de a0+60min
    assert h020.entry(base(), 0, A0) == (None, None)


def test_entry_y_pnl_a_mano():
    tr = base() + [T(A0 + 3601, 0.55), T(A0 + 4000, 0.60), T(A0 + 7200, 0.58), T(A0 + 7201, 0.99),
                   T(A0 + 5000, 0.99, side="SELL"), T(A0 + 5000, 0.45, idx=1)]
    px, med = h020.entry(tr, 0, A0)
    assert px == pytest.approx(0.60) and med == pytest.approx(0.58)
    assert h020.entry(tr, 1, A0) == (pytest.approx(0.45), pytest.approx(0.45))
    # YES a 0.60, comisión 0.02*0.6*0.4 = 0.0048; resuelve YES → 0.3952; NO → −0.6048
    assert h004.pnl(0, px, 0.02, 1.0) == pytest.approx(0.3952)
    assert h004.pnl(0, px, 0.02, 0.0) == pytest.approx(-0.6048)
    assert h004.pnl(1, 0.45, 0.0, 0.5) == pytest.approx(0.05)     # anulado → paga 0.5


class FakeAPI:
    """Devuelve los LIMIT trades más recientes de [a, b], como la Data API."""
    def __init__(self, ts, limit=3):
        self.ts, self.limit, self.calls = sorted(ts), limit, 0

    def __call__(self, cid, a, b):
        self.calls += 1
        w = [t for t in self.ts if a <= t <= b][::-1][: self.limit]
        return [T(t, 0.5) for t in w]


def test_fetch_all_desciende(monkeypatch):
    monkeypatch.setattr(h020, "LIMIT", 3)
    ts = [10, 20, 20, 30, 40, 50, 60, 70]
    api = FakeAPI(ts)
    d, n = h020.fetch_all(api, "c", 0, 100)
    assert sorted(x["timestamp"] for x in d) == ts       # sin duplicados ni pérdidas en el segundo frontera
    assert n == 5


def test_first_trade(monkeypatch):
    monkeypatch.setattr(h020, "LIMIT", 3)
    api = FakeAPI([500, 600, 700, 800, 900])
    assert h020.first_trade(api, "c", 1000, 5000)[0] == 500
    # mercado cuyo trading empieza mucho después de start: ventanas crecientes
    api = FakeAPI([40 * 86400 + 5, 40 * 86400 + 9])
    assert h020.first_trade(api, "c", 0, 50 * 86400)[0] == 40 * 86400 + 5
    assert h020.first_trade(FakeAPI([]), "c", 0, 10 * 86400)[0] is None


def test_null_aleatorio_da_menos_costes():
    """Comprar al azar a precio justo p con y ~ Bernoulli(p) → PnL medio ≈ −comisión media."""
    rng = np.random.default_rng(1)
    p = rng.uniform(0.1, 0.9, 200_000)
    y = (rng.uniform(size=p.size) < p).astype(float)
    idx = rng.integers(0, 2, p.size)
    px = np.where(idx == 0, p, 1 - p)
    pnl = np.array([h004.pnl(i, q, 0.05, yy) for i, q, yy in zip(idx, px, y)])
    assert pnl.mean() == pytest.approx(-(0.05 * px * (1 - px)).mean(), abs=3e-3)


def test_holm_y_p():
    assert h020.holm([0.01, 0.04]) == [True, True]
    assert h020.holm([0.03, 0.04]) == [False, False]
    assert h020.holm([0.02, 0.06]) == [True, False]
    df = pd.DataFrame({"pnl": [1.0, 1.1, 0.9, 1.0], "event_id": [1, 2, 3, 4]})
    assert h020.cluster_p(df) < 1e-6
    df = pd.DataFrame({"pnl": [1.0, -1.0, 1.0, -1.0], "event_id": [1, 2, 3, 4]})
    assert h020.cluster_p(df) == pytest.approx(0.5)
