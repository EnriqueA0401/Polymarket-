from datetime import datetime, timezone

import numpy as np
import pytest

from pmq import h005, h032

U = lambda *a: int(datetime(*a, tzinfo=timezone.utc).timestamp())
H = 3600
D = 86400


def test_parse_bucket():
    assert h032.parse_bucket("<20") == (0, 19)
    assert h032.parse_bucket("20-39") == (20, 39)
    assert h032.parse_bucket("280–299") == (280, 299)
    assert h032.parse_bucket("580+") == (580, None)
    assert h032.parse_bucket("≥580") == (580, None)
    assert h032.parse_bucket("40 or more") == (40, None)
    assert h032.parse_bucket("19 or fewer") == (0, 19)
    assert h032.parse_bucket("less than 40") == (0, 39)
    assert h032.parse_bucket("1,000+") == (1000, None)
    assert h032.parse_bucket("0-4") == (0, 4)
    assert h032.parse_bucket("hola") is None
    assert h032.parse_bucket(None) is None


def test_partition():
    assert h032.buckets_partition([(20, 39), (0, 19), (40, None)])
    assert not h032.buckets_partition([(0, 19), (21, 39), (40, None)])
    assert not h032.buckets_partition([(0, 19), (20, 39)])


def test_parse_window_both_formats_et():
    d1 = "posts on X from November 25 12:00 PM ET to December 2, 2025 12:00 PM ET.  For the purposes"
    a, b = h032.parse_window(d1)
    assert a == U(2025, 11, 25, 17) and b == U(2025, 12, 2, 17)          # EST = UTC−5
    d2 = "posts on X between March 27, 12:00 PM ET and April 3, 2026, 12:00 PM ET."
    a, b = h032.parse_window(d2)
    assert a == U(2026, 3, 27, 16) and b == U(2026, 4, 3, 16)            # EDT = UTC−4
    d3 = "between December 30, 12:00 PM ET and January 6, 2026, 12:00 PM ET"
    a, b = h032.parse_window(d3)
    assert a == U(2025, 12, 30, 17) and b == U(2026, 1, 6, 17)           # cambio de año
    # cambio de hora dentro de la ventana (8 mar 2026): 7 días naturales = 167 h
    d4 = "between March 6, 12:00 PM ET and March 13, 2026, 12:00 PM ET"
    a, b = h032.parse_window(d4)
    assert b - a == 167 * H
    assert h032.parse_window("during the month of November 2025") is None


def test_counts_and_samples_by_hand():
    start = U(2026, 3, 1)
    t = h032.decision_time(start)
    assert t == start + 4 * D
    R = 3 * D
    # 2 posts por día durante 40 días antes de t, importados 1 minuto después (k=1 se importa antes de t)
    created = np.array([t - k * 12 * H + 1 for k in range(1, 81)])
    imported = created + 60
    s = h032.remaining_samples(created, imported, t, R)
    assert list(s) == [6] * 8                      # 3 días × 2/día
    C = h032.current_count(created, imported, start, t)
    assert C == 8                                  # 4 días × 2/día
    assert h032.bucket_prob(C, s, 10, 14) == 1.0
    assert h032.bucket_prob(C, s, 15, None) == 0.0
    assert h032.bucket_prob(C, [0, 1, 2, 3], 9, 10) == 0.5
    assert h032.bucket_prob(C, [0, 1, 2, 3], 11, None) == 0.25


def test_open_ended_bucket_probs_sum_to_one():
    buckets = [(0, 19), (20, 39), (40, 59), (60, None)]
    samples = np.array([0, 5, 17, 25, 33, 41, 60, 99])
    p = [h032.bucket_prob(10, samples, lo, hi) for lo, hi in buckets]
    assert sum(p) == pytest.approx(1.0)
    assert p == [2 / 8, 2 / 8, 2 / 8, 2 / 8]


def test_anti_lookahead_imports_after_t():
    start = U(2026, 3, 1)
    t = h032.decision_time(start)
    R = 3 * D
    rng = np.random.default_rng(1)
    created = np.sort(rng.integers(t - 30 * D, t + 3 * D, 400))
    imported = created + 120
    known = imported <= t
    base_C = h032.current_count(created, imported, start, t)
    base_s = h032.remaining_samples(created, imported, t, R)
    # 1) alterar todo lo importado después de t (contenido, número de posts, timestamps) no cambia nada
    c2 = np.concatenate([created[known], rng.integers(t - 30 * D, t + 3 * D, 999)])
    i2 = np.concatenate([imported[known], t + 1 + rng.integers(0, 10 * D, 999)])
    assert h032.current_count(c2, i2, start, t) == base_C
    assert list(h032.remaining_samples(c2, i2, t, R)) == list(base_s)
    # 2) un backfill tardío (post creado antes de t, importado después) no cuenta
    c3 = np.append(created, t - 10)
    i3 = np.append(imported, t + 3600)
    assert h032.current_count(c3, i3, start, t) == base_C
    # 3) la decisión depende solo de (C, samples, precios en (t, t+30m]): el resultado final no entra
    probs = [h032.bucket_prob(base_C, base_s, lo, hi) for lo, hi in [(0, 99), (100, None)]]
    d = [h032.decide(p, 0.5, 0.5, 0.04) for p in probs]
    probs2 = [h032.bucket_prob(h032.current_count(c2, i2, start, t), h032.remaining_samples(c2, i2, t, R), lo, hi)
              for lo, hi in [(0, 99), (100, None)]]
    assert [h032.decide(p, 0.5, 0.5, 0.04)[0] for p in probs2] == [x[0] for x in d]


def test_history_ok():
    start = U(2026, 3, 1)
    t = h032.decision_time(start)
    R = 3 * D
    assert h032.history_ok(start - 1, t - 24 * D, start, t, R)
    assert not h032.history_ok(start + 1, t - 30 * D, start, t, R)     # tracker no vivo al inicio
    assert not h032.history_ok(start - 1, t - 20 * D, start, t, R)     # historial < 8R


def test_decision_and_pnl_by_hand():
    # prob 0.9, YES a 0.70, comisión 0.04 → edge = 0.9 − 0.7 − 0.04·0.7·0.3 = 0.1916
    side, px, e = h032.decide(0.9, 0.70, 0.35, 0.04)
    assert side == "YES" and px == 0.70 and e == pytest.approx(0.1916)
    assert h005.pnl("YES", 0.70, 0.04, 1.0) == pytest.approx(1 - 0.70 - 0.0084)
    assert h005.pnl("YES", 0.70, 0.04, 0.0) == pytest.approx(-0.70 - 0.0084)
    # prob 0 → NO a 0.80: edge 1 − 0.8 − 0.04·0.16 = 0.1936
    side, px, e = h032.decide(0.0, 0.05, 0.80, 0.04)
    assert side == "NO" and e == pytest.approx(0.1936)
    # edge por debajo de θ = 0.05 → no apuesta
    assert h032.decide(0.53, 0.50, 0.52, 0.04)[0] is None


def test_final_count_half_open():
    start, end = 0, 100
    assert h032.final_count([0, 50, 99, 100, -1], start, end) == 3


def test_null_random_bets_lose_costs():
    """Test nulo: precios justos (y ~ Bernoulli(px)) y lado al azar → PnL medio ≈ −comisión."""
    rng = np.random.default_rng(0)
    n = 200_000
    px = rng.uniform(0.05, 0.95, n)
    y = (rng.random(n) < px).astype(float)
    side_yes = rng.random(n) < 0.5
    tok = np.where(side_yes, px, 1 - px)
    pnl = np.array([h005.pnl("YES" if s else "NO", p, 0.04, yy) for s, p, yy in zip(side_yes, tok, y)])
    fee = 0.04 * tok * (1 - tok)
    assert abs(pnl.mean() + fee.mean()) < 0.004
