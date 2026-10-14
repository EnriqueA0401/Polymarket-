import pandas as pd
import pytest
from pmq import football as F


def test_sim_nombres():
    assert F.sim("Coventry City FC", "Coventry") >= 0.85
    assert F.sim("Olympique de Marseille", "Marseille") >= 0.85
    assert F.sim("Liverpool FC", "Everton") < 0.6


def test_fair_prob_sin_margen():
    row = {"PSH": 2.0, "PSD": 4.0, "PSA": 4.0, "side": "H"}
    assert F.fair_prob(row) == pytest.approx(0.5)
    row = {"PSH": 1.9, "PSD": 3.8, "PSA": 3.8, "side": "A"}
    assert F.fair_prob(row) == pytest.approx(0.25)


def test_match_ambiguo_y_ok():
    fd = pd.DataFrame({"league": ["E0", "E0"], "date": pd.to_datetime(["2025-08-15", "2025-08-15"]),
                       "HomeTeam": ["Liverpool", "Man United"], "AwayTeam": ["Bournemouth", "Man City"],
                       "kickoff": pd.to_datetime(["2025-08-15 19:00", "2025-08-15 14:00"], utc=True), "FTR": ["H", "D"]})
    pm = pd.DataFrame({"id": [1, 2], "question": ["Will Liverpool FC win on 2025-08-15?", "Will Chelsea FC win on 2025-08-15?"],
                       "series": ["epl", "epl"]})
    r = F.match_markets(pm, fd).set_index("id")
    assert r.loc[1, "status"] == "ok" and r.loc[1, "side"] == "H"
    assert r.loc[2, "status"] == "ambiguo"  # Chelsea no juega ese día en E0


def test_clubes_misma_ciudad_no_se_confunden():
    assert F.sim("Paris Saint-Germain FC", "Paris FC") < 0.85
    assert F.sim("Paris Saint-Germain FC", "Paris SG") == 1.0
    assert F.sim("Dundee United FC", "Dundee") < 0.85
    assert F.sim("Sheffield Wednesday FC", "Sheffield United") < F.MIN_SCORE
    assert F.sim("Manchester City FC", "Man City") == 1.0


def test_palabras_genericas_no_emparejan():
    assert F.sim("Real Oviedo", "Sociedad") < F.MIN_SCORE
    assert F.sim("Bolton Wanderers FC", "Wolves") < F.MIN_SCORE
    assert F.sim("Real Oviedo", "Oviedo") >= F.MIN_SCORE
