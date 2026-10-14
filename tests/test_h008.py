import pandas as pd
import pytest
from pmq import h008


def test_trade_pnl():
    assert h008.trade_pnl("BUY", 0, 0.4, 10, 1.0) == pytest.approx(6.0)
    assert h008.trade_pnl("BUY", 1, 0.4, 10, 1.0) == pytest.approx(-4.0)
    assert h008.trade_pnl("SELL", 0, 0.7, 10, 0.0) == pytest.approx(7.0)
    assert h008.trade_pnl("BUY", 0, 0.4, 10, 0.5) == pytest.approx(1.0)


def test_rank_requiere_minimos():
    rows = [{"proxyWallet": "a", "pnl": 1.0, "event_id": i} for i in range(25)]
    rows += [{"proxyWallet": "b", "pnl": 100.0, "event_id": 1} for _ in range(25)]   # 1 solo evento
    r = h008.rank_wallets(pd.DataFrame(rows))
    assert list(r.index) == ["a"]


def test_copy_price_respeta_retraso():
    t = [{"outcomeIndex": 0, "side": "BUY", "price": 0.5, "timestamp": 30},
         {"outcomeIndex": 0, "side": "BUY", "price": 0.55, "timestamp": 100},
         {"outcomeIndex": 0, "side": "BUY", "price": 0.9, "timestamp": 2000},
         {"outcomeIndex": 1, "side": "BUY", "price": 0.6, "timestamp": 100}]
    assert h008.copy_price(t, 0, 0) == 0.55
    assert h008.copy_price(t, 0, 5000) is None
