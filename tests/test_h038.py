import numpy as np
import pandas as pd
import pytest

from pmq import h038

T = 1_700_000_000.0


def tr(rows):
    """rows: (segundos respecto a T, yes_price, taker_outcome_side, count)."""
    raw = [{"created_time": pd.Timestamp(T + s, unit="s", tz="UTC").isoformat(),
            "yes_price_dollars": f"{p:.4f}", "taker_outcome_side": side, "count_fp": f"{c:.2f}",
            "is_block_trade": False} for s, p, side, c in rows]
    return raw


# ------------------------------------------------------------------ comisiones (a mano)
def test_fee_a_mano():
    # 100 contratos a 0.95: 0.07·100·0.95·0.05 = 0.3325 USD → ceil al céntimo = 0.34
    assert h038.kalshi_fee(100, 0.95) == pytest.approx(0.34)
    # 1 contrato a 0.95: 0.0033 → 0.01 (el redondeo pesa mucho en órdenes pequeñas)
    assert h038.kalshi_fee(1, 0.95) == pytest.approx(0.01)
    # 100 a 0.50: 0.07·100·0.25 = 1.75 exacto (sin subir un céntimo por coma flotante)
    assert h038.kalshi_fee(100, 0.50) == pytest.approx(1.75)
    # multiplicador 0.5 (p. ej. índices): 0.035·100·0.95·0.05 = 0.16625 → 0.17
    assert h038.kalshi_fee(100, 0.95, mult=0.5) == pytest.approx(0.17)
    assert h038.kalshi_fee(100, 0.95, mult=0.0) == 0.0
    # simétrica en p ↔ 1−p
    assert h038.kalshi_fee(37, 0.12) == h038.kalshi_fee(37, 0.88)


def test_pnl_a_mano():
    # compra YES a 0.95, 100 contratos, gana: 1 − 0.95 − 0.34/100 = 0.0466
    assert h038.pnl_per_contract("yes", 0.95, "yes") == pytest.approx(0.0466)
    # pierde: −0.95 − 0.0034
    assert h038.pnl_per_contract("yes", 0.95, "no") == pytest.approx(-0.9534)
    # compra NO a 0.93, resultado no: 1 − 0.93 − ceil(0.07·100·0.93·0.07=0.4557)=0.46/100
    assert h038.pnl_per_contract("no", 0.93, "no") == pytest.approx(1 - 0.93 - 0.0046)
    # anulado: solo se pierde la comisión
    assert h038.pnl_per_contract("no", 0.93, "void") == pytest.approx(-0.0046)
    # costes ×2: comisión doble y +0.01 de precio: 1 − 0.96 − 2·ceil(0.07·100·.96·.04=0.2688)/100
    assert h038.pnl_per_contract("yes", 0.95, "yes", fee_mult=2, extra_slip=0.01) == pytest.approx(
        1 - 0.96 - 2 * 0.27 / 100)


# ------------------------------------------------------------------ señal y ejecución
def test_decide_yes_peor_precio():
    t = T
    d = h038.decide(h038.norm_trades(tr([(-5000, 0.80, "yes", 5),       # fuera de ventana
                                         (-3000, 0.93, "yes", 10),      # compra YES a 0.93
                                         (-2000, 0.96, "yes", 3),       # peor compra YES
                                         (-1500, 0.90, "no", 7),        # compra NO (lado contrario)
                                         (-10, 0.92, "no", 1)])), t)
    assert d["p_yes"] == pytest.approx(0.92) and d["side"] == "yes"
    assert d["exec_price"] == pytest.approx(0.96)
    assert d["n_side"] == 2 and d["vol_side"] == pytest.approx(13)


def test_decide_no_lado_no():
    d = h038.decide(h038.norm_trades(tr([(-3000, 0.06, "no", 4),          # compra NO a 0.94
                                         (-100, 0.08, "yes", 2),          # compra YES (no cuenta)
                                         (-50, 0.07, "no", 1)])), T)      # compra NO a 0.93
    assert d["side"] == "no" and d["p_yes"] == pytest.approx(0.07)
    assert d["exec_price"] == pytest.approx(0.94)
    assert d["ref_price"] == pytest.approx(0.93)


def test_sin_compra_del_lado_no_hay_precio():
    d = h038.decide(h038.norm_trades(tr([(-100, 0.95, "no", 2)])), T)    # solo ventas de YES
    assert d["side"] == "yes" and np.isnan(d["exec_price"])
    d = h038.decide(h038.norm_trades(tr([(-100, 0.50, "yes", 2)])), T)
    assert d["side"] is None


def test_block_trades_excluidos():
    raw = tr([(-100, 0.95, "yes", 2)])
    raw[0]["is_block_trade"] = True
    assert len(h038.norm_trades(raw)) == 0


def test_anti_lookahead():
    base = [(-3000, 0.93, "yes", 10), (-200, 0.95, "yes", 3)]
    d0 = h038.decide(h038.norm_trades(tr(base)), T)
    # añadir trades posteriores a t (incluido uno en t+1 s muy distinto) no cambia nada
    d1 = h038.decide(h038.norm_trades(tr(base + [(1, 0.01, "no", 999), (5000, 0.99, "yes", 50)])), T)
    assert d0 == d1
    # el trade exactamente en t sí cuenta (ventana (t−1h, t])
    d2 = h038.decide(h038.norm_trades(tr(base + [(0, 0.97, "yes", 1)])), T)
    assert d2["exec_price"] == pytest.approx(0.97)
    # y el de t−1h exacto no
    d3 = h038.decide(h038.norm_trades(tr([(-3600, 0.99, "yes", 1), (-10, 0.95, "yes", 1)])), T)
    assert d3["exec_price"] == pytest.approx(0.95)


def test_schedule_ref_prefiere_expected():
    m = {"close_time": "2025-01-02T03:31:47Z", "expected_expiration_time": "2025-01-02T03:30:00Z"}
    assert h038.schedule_ref(m) == pd.Timestamp("2025-01-02T03:30:00Z")
    assert h038.schedule_ref({"close_time": "2025-01-02T00:00:00Z"}) == pd.Timestamp("2025-01-02", tz="UTC")


def test_nulo_azar_da_menos_costes():
    """Si el precio es justo (resultado ~ Bernoulli(precio)), comprar da ≈ −comisión."""
    rng = np.random.default_rng(1)
    p = rng.uniform(0.9, 0.99, 200_000)
    y = rng.uniform(size=p.size) < p
    pnl = np.array([h038.pnl_per_contract("yes", q, "yes" if w else "no") for q, w in zip(p[:20000], y[:20000])])
    fee = np.mean([h038.kalshi_fee(100, q) / 100 for q in p[:20000]])
    assert pnl.mean() == pytest.approx(-fee, abs=0.004)


def test_ev_hash_determinista():
    assert h038.ev_hash("KXFOO-25JAN01") == h038.ev_hash("KXFOO-25JAN01")
    assert 0 <= h038.ev_hash("x") < 1
