import pandas as pd
import pytest
from pmq import h010


def bk(p, s=1000):
    return {"asks": [{"price": str(p), "size": str(s)}]}


def test_pair_escalera_incoherente():
    ev = {"id": "e", "title": "t", "markets": [
        {"question": "X by June?", "endDate": "2030-06-30T00:00:00Z", "clobTokenIds": '["y1", "n1"]', "feesEnabled": False},
        {"question": "X by March?", "endDate": "2030-03-31T00:00:00Z", "clobTokenIds": '["y0", "n0"]', "feesEnabled": False}]}
    # P(marzo)=0.5 (NO marzo cuesta 0.5) y YES junio cuesta 0.45 → coste 0.95 < 1
    books = {"n0": bk(0.50), "y1": bk(0.45)}
    r = h010.pairs(ev, books, pd.Timestamp("2030-01-01", tz="UTC"))
    assert len(r) == 1 and r[0]["d1"].startswith("2030-03")
    assert r[0]["ret"] == pytest.approx((50 - 47.5) / 47.5)


def test_preguntas_distintas_no_se_emparejan():
    ev = {"id": "e", "title": "t", "markets": [
        {"question": "Will it snow in Dallas by Nov 30?", "endDate": "2030-11-30T00:00:00Z", "clobTokenIds": '["y1", "n1"]'},
        {"question": "Will it snow in Chicago by Nov 15?", "endDate": "2030-11-15T00:00:00Z", "clobTokenIds": '["y0", "n0"]'}]}
    assert h010.pairs(ev, {}, pd.Timestamp("2030-01-01", tz="UTC")) == []
