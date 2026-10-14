import pandas as pd
import pytest
from pmq import h004


def test_fav_y_tradable():
    assert h004.fav_side(0.97) == 0 and h004.fav_side(0.02) == 1 and h004.fav_side(0.5) is None
    assert h004.tradable(0.96) and not h004.tradable(0.94) and not h004.tradable(0.996) and not h004.tradable(None)


def test_pnl_a_mano():
    assert h004.pnl(0, 0.97, 0.0, 1.0) == pytest.approx(0.03)
    assert h004.pnl(1, 0.97, 0.0, 1.0) == pytest.approx(-0.97)
    assert h004.pnl(0, 0.97, 0.07, 0.5) == pytest.approx(0.5 - 0.97 - 0.07 * 0.97 * 0.03)


def test_drop_top():
    df = pd.DataFrame({"pnl": [10, 1, 1, -1], "event_id": ["a", "b", "c", "d"]})
    assert h004.drop_top(df, k=1) == pytest.approx(1 / 3)
