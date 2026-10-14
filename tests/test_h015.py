from pmq import h015


def test_winner_idx():
    assert h015.winner_idx("H", "H") == 0
    assert h015.winner_idx("D", "H") == 1
    assert h015.winner_idx("H", "A") == 1
