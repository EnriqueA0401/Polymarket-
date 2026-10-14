"""H015 — comprar al ganador tras el final del partido (fútbol)."""
import pandas as pd

AFTER, WINDOW, MAXPX = pd.Timedelta("3h"), 7200, 0.995


def winner_idx(ftr, side):
    """Token ganador del mercado "Will <equipo> win?": 0 (YES) si el equipo ganó, 1 (NO) si empató o perdió."""
    return 0 if ftr == side else 1
