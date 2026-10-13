import pandas as pd
import pytest
from pmq import h003

T0 = pd.Timestamp("2025-01-10", tz="UTC")


def test_traded_before_ignora_futuro():
    t = T0.timestamp()
    h = [{"t": t - 100, "p": 0.5}, {"t": t + 100, "p": 0.6}]
    assert not h003.traded_before(h, t)
    h.append({"t": t - 50, "p": 0.55})
    assert h003.traded_before(h, t)


def test_trades_pnl_a_mano():
    obs = pd.DataFrame(dict(id=[1, 2], event_id=["a", "b"], p=[0.6, 0.9], y=[0.0, 0.0], fee_rate=[0.0, 0.0]))
    tr = h003.trades(obs)
    assert len(tr) == 1                                  # p=0.9 fuera de rango
    q = 0.4 + 0.02
    assert tr.ret.iloc[0] == pytest.approx((1 - q) / q)
