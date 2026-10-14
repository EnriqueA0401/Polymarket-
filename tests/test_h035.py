import numpy as np
import pytest

from pmq import h035


def test_keccak_vectors():
    assert h035.keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert h035.keccak256(b"abc").hex() == "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"
    # bloque múltiple (> 136 bytes de rate)
    assert h035.keccak256(b"a" * 300).hex() == "5b7e0e47a96f32a88b4f14ca177982790807c40e1a105742ba0fc1babe1ef826"
    assert h035.topic("Transfer(address,uint256,uint256)") != h035.topic("Transfer(address,address,uint256)")
    assert h035.topic("Transfer(address,address,uint256)") == \
        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _w(x):
    return (x % (1 << 256)).to_bytes(32, "big")


def _log(anc: bytes, price, ts=1_700_000_000, block=100, li=0, req="ab" * 20):
    data = b"Y" * 32 + _w(1_699_999_000) + _w(4 * 32) + _w(price) + _w(len(anc)) + anc + b"\x00" * (-len(anc) % 32)
    return {"address": h035.OO[1].upper().replace("0X", "0x"), "data": "0x" + data.hex(),
            "topics": [h035.T_DISPUTE, "0x" + "0" * 24 + req, "0x" + "0" * 24 + "cd" * 20, "0x" + "0" * 24 + "ef" * 20],
            "blockNumber": hex(block), "blockTimestamp": hex(ts), "transactionHash": "0x01", "logIndex": hex(li)}


def test_decode_dispute():
    anc = b"q: title: Will X happen?, res_data: p1: 0, p2: 1, p3: 0.5,initializer:abc"
    d = h035.decode_dispute(_log(anc, 10 ** 18))
    assert d["proposed_price"] == 10 ** 18
    assert d["qid"] == "0x" + h035.keccak256(anc).hex()
    assert d["ts"] == 1_700_000_000 and d["block"] == 100 and d["req_ts"] == 1_699_999_000
    assert d["requester"] == "0x" + "ab" * 20 and d["disputer"] == "0x" + "ef" * 20
    assert d["oo"] == h035.OO[1]
    assert d["ancillary"].startswith("q: title")
    assert h035.decode_dispute(_log(anc, 0))["proposed_price"] == 0
    assert h035.decode_dispute(_log(anc, -(2 ** 255)))["proposed_price"] == -(2 ** 255)   # "too early"


def test_side_of_price():
    assert h035.side_of_price(10 ** 18) == 0
    assert h035.side_of_price(0) == 1
    assert h035.side_of_price(5 * 10 ** 17) is None
    assert h035.side_of_price(-(2 ** 255)) is None


def test_first_disputes():
    ds = [{"qid": "0xA", "ts": 20, "block": 2, "log_index": 0, "proposed_price": 0},
          {"qid": "0xa", "ts": 10, "block": 1, "log_index": 3, "proposed_price": 10 ** 18},
          {"qid": "0xb", "ts": 5, "block": 1, "log_index": 0, "proposed_price": 0}]
    f = h035.first_disputes(ds, ["0xa"])
    assert set(f) == {"0xa"} and f["0xa"]["ts"] == 10 and f["0xa"]["proposed_price"] == 10 ** 18


def T(idx, px, ts, side="BUY"):
    return {"outcomeIndex": idx, "side": side, "price": px, "size": 10, "timestamp": ts}


def test_entry_window_and_cap():
    td = 1_000_000
    t0 = td + 1800
    tr = [T(0, 0.50, t0), T(0, 0.60, t0 + 1), T(0, 0.70, t0 + 7200), T(0, 0.99, t0 + 7201),
          T(1, 0.97, t0 + 10), T(0, 0.80, t0 + 20, "SELL"), T(0, 0.98, td + 100)]
    assert h035.entry(tr, 0, td) == (0.70, "ok")           # peor compra en (t0, t0+2h]; t0 excluido
    assert h035.entry(tr, 1, td) == (None, "px>max")       # 0.97 > 0.95
    assert h035.entry([], 0, td) == (None, "sin_trade")


def test_anti_lookahead():
    """Cambiar trades fuera de (t, t+2h] o el resultado final no cambia la decisión ni el precio."""
    rng = np.random.default_rng(1)
    td = 5_000_000
    t0 = td + h035.DELAY_S
    inside = [T(int(rng.integers(0, 2)), round(float(rng.uniform(.05, .95)), 2), t0 + int(rng.integers(1, 7201)))
              for _ in range(30)]
    base = [h035.entry(inside, i, td) for i in (0, 1)]
    for _ in range(20):
        noise = [T(int(rng.integers(0, 2)), round(float(rng.uniform(.01, .99)), 2),
                   int(rng.choice([rng.integers(0, t0 + 1), rng.integers(t0 + 7201, t0 + 10 ** 6)]))) for _ in range(50)]
        assert [h035.entry(inside + noise, i, td) for i in (0, 1)] == base
    # el resultado y solo entra en el PnL, después de fijar precio
    px, _ = base[0] if base[0][0] is not None else (0.5, "ok")
    assert h035.pnl(0, px, 0.0, 1.0) - h035.pnl(0, px, 0.0, 0.0) == pytest.approx(1.0)


def test_pnl_hand():
    # compra YES a 0.80, comisión 0.04·0.8·0.2 = 0.0064; gana → 1 − 0.8 − 0.0064
    assert h035.pnl(0, 0.80, 0.04, 1.0) == pytest.approx(0.1936)
    assert h035.pnl(0, 0.80, 0.04, 0.0) == pytest.approx(-0.8064)
    # NO a 0.30 con y = 0 → gana
    assert h035.pnl(1, 0.30, 0.0, 0.0) == pytest.approx(0.70)
    # anulado 50-50: pago 0.5
    assert h035.pnl(1, 0.30, 0.0, 0.5) == pytest.approx(0.20)


def test_null_random_side_gives_minus_costs():
    """Lado al azar a precio justo (= prob. real) → PnL medio ≈ −comisión."""
    rng = np.random.default_rng(0)
    n = 200_000
    p = rng.uniform(0.05, 0.95, n)
    y = (rng.uniform(size=n) < p).astype(float)
    idx = rng.integers(0, 2, n)
    px = np.where(idx == 0, p, 1 - p)
    rate = 0.05
    pn = np.array([h035.pnl(int(i), float(q), rate, float(v)) for i, q, v in zip(idx, px, y)])
    assert pn.mean() == pytest.approx(-(rate * px * (1 - px)).mean(), abs=0.004)
