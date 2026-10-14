import pandas as pd
import pytest
from pmq import h037


def bk(p):
    return {"asks": [{"price": str(p), "size": "1000"}]}


def test_strike_y_plantilla():
    assert h037.strike("Will BTC be above $120,000 on Oct 31?") == 120000
    assert h037.strike("Will ETH reach $5k?") == 5000
    assert h037.template("Will BTC be above $120,000 on Oct 31?") == h037.template("Will BTC be above $130,000 on Oct 31?")


def test_par_incoherente_above():
    ms = [{"question": "Will BTC be above $120,000 on Oct 31?", "endDate": "x", "clobTokenIds": '["y1","n1"]', "acceptingOrders": True},
          {"question": "Will BTC be above $130,000 on Oct 31?", "endDate": "x", "clobTokenIds": '["y2","n2"]', "acceptingOrders": True}]
    r = h037.pairs({"id": "e", "markets": ms}, {"y1": bk(0.40), "n2": bk(0.55)}, pd.Timestamp("2030-01-01", tz="UTC"))
    assert len(r) == 1 and r[0]["ret"] == pytest.approx((50 - 47.5) / 47.5)   # sin feesEnabled → comisión 0


def test_direccion_low_high():
    assert h037.direction("Will WTI hit (LOW) $65 Week of October 12?") == -1
    assert h037.direction("Will WTI hit (HIGH) $95 Week of October 12?") == 1
    assert h037.direction("Will BTC dip to $90,000?") == -1


def test_under_management_no_es_bajista():
    assert h037.direction("Will Blackstone (BX) Q3 total assets under management be above $1.40T?") == 1
    assert h037.strike("above $1.40T") == 1.40e12
