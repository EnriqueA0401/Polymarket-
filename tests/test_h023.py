import numpy as np
import pandas as pd
import pytest

from pmq import h023 as H


def test_pm_full_names_and_alias():
    d = ("In the upcoming NFL game, scheduled for November 2 at 4:05PM ET:\n"
         "If Jacksonville Jaguars wins, the market will resolve to “Jaguars”.\n"
         "If Las Vegas Raiders wins, the market will resolve to “Raiders”.")
    assert H.pm_full_names(d, ["Jaguars", "Raiders"], "NFL") == ["Jacksonville Jaguars", "Las Vegas Raiders"]
    assert H.pm_full_names(d, ["Jaguars", "Bears"], "NFL") == ["Jacksonville Jaguars", "Chicago Bears"]
    assert H.pm_full_names(d, ["Jaguars", "Foo"], "NFL") is None
    # sin descripción útil: apodos
    assert H.pm_full_names("", ["Clippers", "Trail Blazers"], "NBA") == ["Los Angeles Clippers", "Portland Trail Blazers"]
    assert H.pm_full_names("", ["Sox", "Cubs"], "MLB") is None        # ambiguo (Red Sox / White Sox)
    d2 = 'If Oakland Athletics win, the market will resolve to "Athletics". If Texas Rangers win, the market will resolve to "Texas Rangers".'
    assert H.pm_full_names(d2, ["Athletics", "Texas Rangers"], "MLB") == ["Athletics", "Texas Rangers"]


def _kmk(ev, code, res):
    return {"ticker": f"{ev}-{code}", "event_ticker": ev, "result": res, "close_time": "x", "open_time": "y",
            "settlement_value_dollars": "1"}


def test_match_by_date_and_teams():
    ms = [_kmk("KXNFLGAME-25NOV02JACLV", "JAC", "yes"), _kmk("KXNFLGAME-25NOV02JACLV", "LV", "no")]
    kev = H.k_events(ms, "NFL")
    assert len(kev) == 1 and kev[0]["date"].isoformat() == "2025-11-02"
    desc = ("If Las Vegas Raiders wins, the market will resolve to “Raiders”. "
            "If Jacksonville Jaguars wins, the market will resolve to “Jaguars”.")
    pm = pd.DataFrame([
        # 21:05 UTC = 16:05 ET mismo día → ok; outcome0 = Raiders → ticker LV
        {"id": 1, "league": "NFL", "o0": "Raiders", "o1": "Jaguars", "description": desc,
         "game_start": pd.Timestamp("2025-11-02 21:05", tz="UTC")},
        # 02:00 UTC del 3 = 21:00 ET del 2 → ok (fecha ET)
        {"id": 2, "league": "NFL", "o0": "Jaguars", "o1": "Raiders", "description": desc,
         "game_start": pd.Timestamp("2025-11-03 02:00", tz="UTC")},
        # otra fecha → sin Kalshi
        {"id": 3, "league": "NFL", "o0": "Jaguars", "o1": "Raiders", "description": desc,
         "game_start": pd.Timestamp("2025-11-09 18:00", tz="UTC")},
    ])
    m = H.match(pm, kev).set_index("id")
    assert m.loc[1, "status"] == "ok" and m.loc[1, "k_ticker0"].endswith("-LV") and m.loc[1, "k_result0"] == "no"
    assert m.loc[2, "status"] == "ok" and m.loc[2, "k_ticker0"].endswith("-JAC")
    assert m.loc[3, "status"] == "no_kalshi"


def test_k_candidates_hand():
    # Kalshi: 0.50 en t=0, 0.52 en t=60, 0.56 en t=150 → en t=150, K(t−120=30)=0.50 → Δ=0.06 ≥ 0.05
    kt = np.array([0., 60., 150., 400.])
    kp = np.array([.50, .52, .56, .56])
    c = H.k_candidates(kt, kp, game_start=10_000)
    assert [round(x[0]) for x in c] == [150] and abs(c[0][1] - 0.06) < 1e-9
    # Inicio del partido: t + 300 debe ser ≤ game_start → con game_start = 449 no hay señal
    assert H.k_candidates(kt, kp, game_start=449) == []
    assert len(H.k_candidates(kt, kp, game_start=450)) == 1
    # Desplazamiento placebo de −10 min: mismos candidatos, tiempos − 600
    c2 = H.k_candidates(kt, kp, game_start=10_000, shift=-600)
    assert [round(x[0]) for x in c2] == [-450]


def test_signals_pm_filter_and_refractory():
    cands = [(1000., 0.06), (1100., 0.07), (1400., -0.05)]
    # PM quieto: trades en 500 (0.50) y 950 (0.51)
    pt, pp = np.array([500., 950.]), np.array([.50, .51])
    s = H.signals(cands, pt, pp)
    # 1000 → señal (|0.51−0.50|<0.02); 1100 refractario; 1400 → PM(1280)=0.51, PM(1400)=0.51 → señal NO
    assert [x["t"] for x in s] == [1000., 1400.] and [x["idx"] for x in s] == [0, 1]
    # PM ya se movió 0.03 en la ventana → sin señal
    pt2, pp2 = np.array([500., 950.]), np.array([.50, .53])
    assert H.signals([(1000., 0.06)], pt2, pp2) == []
    # PM(t−120) desconocido (sin trades en la hora previa) → sin señal
    assert H.signals([(10000., 0.06)], np.array([500.]), np.array([.5])) == []


def test_anti_lookahead():
    """Alterar datos posteriores a t no cambia la decisión en t."""
    rng = np.random.default_rng(0)
    kt = np.sort(rng.uniform(0, 5000, 400)); kp = np.round(0.5 + np.cumsum(rng.normal(0, .01, 400)), 2)
    pt = np.sort(rng.uniform(0, 5000, 300)); pp = np.round(0.5 + np.cumsum(rng.normal(0, .005, 300)), 3)
    T = 2500.
    s1 = [x for x in H.signals(H.k_candidates(kt, kp, 1e9), pt, pp) if x["t"] <= T]
    kp2, pp2 = kp.copy(), pp.copy()
    kp2[kt > T] = rng.uniform(0, 1, (kt > T).sum()); pp2[pt > T] = rng.uniform(0, 1, (pt > T).sum())
    s2 = [x for x in H.signals(H.k_candidates(kt, kp2, 1e9), pt, pp2) if x["t"] <= T]
    assert s1 == s2 and len(s1) > 0


def test_pm_series_and_exec_and_pnl():
    tr = [{"timestamp": 10, "price": 0.40, "outcomeIndex": 0, "side": "BUY"},
          {"timestamp": 20, "price": 0.55, "outcomeIndex": 1, "side": "BUY"},
          {"timestamp": 40, "price": 0.62, "outcomeIndex": 1, "side": "BUY"},
          {"timestamp": 50, "price": 0.70, "outcomeIndex": 1, "side": "SELL"}]
    t, p = H.pm_series(tr)
    assert list(t) == [10, 20, 40, 50] and np.allclose(p, [.40, .45, .38, .30])
    assert H.exec_price(tr, 1, 20, 50) == 0.62          # (20, 50]: excluye 20, solo BUY
    assert H.exec_price(tr, 0, 10, 50) is None
    # comprar token 1 a 0.62 con rate 0.05, y = 0 (gana outcome1): 1 − 0.62 − 0.05·0.62·0.38
    assert H.pnl(1, 0.62, 0.05, 0.0) == pytest.approx(0.38 - 0.01178)
    assert H.pnl(1, 0.62, 0.05, 1.0, cost_mult=2) == pytest.approx(-0.62 - 0.02356)


def test_null_random_entries_lose_costs():
    """Test nulo: comprar al precio justo un lado al azar → PnL medio ≈ −comisión."""
    rng = np.random.default_rng(1)
    n = 200_000
    q = rng.uniform(0.2, 0.8, n); y = (rng.uniform(size=n) < q).astype(float)
    idx = rng.integers(0, 2, n)
    px = np.where(idx == 0, q, 1 - q)
    r = np.array([H.pnl(i, p, 0.05, yy) for i, p, yy in zip(idx, px, y)])
    exp = -(0.05 * px * (1 - px)).mean()
    assert abs(r.mean() - exp) < 0.004
