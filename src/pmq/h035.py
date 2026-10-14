"""H035 — ventana de disputa UMA: comprar el lado propuesto tras la (primera) disputa.

Datos on-chain (Polygon):
- Polymarket pide precios al Optimistic Oracle V2 de UMA (0xee3a…7c24) y, desde 2025-09, al
  Managed Optimistic Oracle V2 (0x2c03…58b1); ambas direcciones verificadas con eth_call
  `optimisticOracle()` sobre cada adaptador (UmaCtfAdapter / NegRiskUmaCtfAdapter).
- Evento DisputePrice(address indexed requester, address indexed proposer, address indexed disputer,
  bytes32 identifier, uint256 timestamp, bytes ancillaryData, int256 proposedPrice).
  La hora de la disputa es el blockTimestamp del log; `proposedPrice` es la propuesta disputada.
- questionID del adaptador = keccak256(ancillaryData) (el adaptador añade "initializer:…" al
  ancillary antes de hashear y lo envía tal cual al OO).
- Precio → resultado (UmaCtfAdapter._constructPayouts): 1e18 → payouts [1,0] (gana outcome 0 =
  token YES, idx 0); 0 → [0,1] (idx 1); 0.5e18 → [1,1] (50-50, sin lado). Se verifica en G1 con
  QuestionResolved(settledPrice) frente al resultado de Gamma.
"""
import json, os, time
import requests

from pmq import h004, h005

OO = ("0xee3afe347d5c74317041e2618c49534daf887c24",   # OptimisticOracleV2 (Polygon)
      "0x2c0367a9db231ddebd88a94b4f6461a6e47c58b1")   # ManagedOptimisticOracleV2 (Polygon)
RPC = ("https://gateway.tenderly.co/public/polygon", "https://polygon.gateway.tenderly.co")
ONE = 10 ** 18
DELAY_S = 30 * 60          # t = disputa + 30 min
WINDOW_S = 2 * 3600        # entrada = peor compra taker en (t, t + 2 h]
MAX_PX = 0.95              # solo si precio ≤ 0.95

# ---------------------------------------------------------------- keccak-256 (Ethereum, sin dependencias)
_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
       0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
       0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
       0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
       0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M = (1 << 64) - 1


def _rol(x, n):
    return ((x << n) | (x >> (64 - n))) & _M if n else x


def _f(A):
    for rc in _RC:
        C = [A[x][0] ^ A[x][1] ^ A[x][2] ^ A[x][3] ^ A[x][4] for x in range(5)]
        D = [C[(x - 1) % 5] ^ _rol(C[(x + 1) % 5], 1) for x in range(5)]
        A = [[A[x][y] ^ D[x] for y in range(5)] for x in range(5)]
        B = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                B[y][(2 * x + 3 * y) % 5] = _rol(A[x][y], _ROT[x][y])
        A = [[B[x][y] ^ ((~B[(x + 1) % 5][y]) & B[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        A[0][0] ^= rc
    return A


def keccak256(data: bytes) -> bytes:
    rate = 136
    p = bytearray(data) + b"\x01"
    p += b"\x00" * (-len(p) % rate)
    p[-1] |= 0x80
    A = [[0] * 5 for _ in range(5)]
    for o in range(0, len(p), rate):
        blk = p[o:o + rate]
        for i in range(rate // 8):
            A[i % 5][i // 5] ^= int.from_bytes(blk[8 * i:8 * i + 8], "little")
        A = _f(A)
    return b"".join(A[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


def topic(sig):
    return "0x" + keccak256(sig.encode()).hex()


T_DISPUTE = topic("DisputePrice(address,address,address,bytes32,uint256,bytes,int256)")
T_RESOLVED = topic("QuestionResolved(bytes32,int256,uint256[])")

# ---------------------------------------------------------------- decodificación ABI


def _int256(word: bytes) -> int:
    v = int.from_bytes(word, "big")
    return v - (1 << 256) if v >> 255 else v


def decode_dispute(log):
    """Log DisputePrice → dict. data = identifier | timestamp | offset(ancillary) | proposedPrice | bytes."""
    d = bytes.fromhex(log["data"][2:])
    w = lambda i: d[32 * i:32 * i + 32]
    off = int.from_bytes(w(2), "big")
    n = int.from_bytes(d[off:off + 32], "big")
    anc = d[off + 32:off + 32 + n]
    tp = log["topics"]
    return {"oo": log["address"].lower(), "requester": "0x" + tp[1][-40:], "proposer": "0x" + tp[2][-40:],
            "disputer": "0x" + tp[3][-40:], "req_ts": int.from_bytes(w(1), "big"),
            "proposed_price": _int256(w(3)), "qid": "0x" + keccak256(anc).hex(),
            "block": int(log["blockNumber"], 16), "ts": int(log["blockTimestamp"], 16),
            "tx": log["transactionHash"], "log_index": int(log["logIndex"], 16),
            "ancillary": anc.decode("utf-8", "replace")}


def decode_resolved(log):
    tp = log["topics"]
    return {"adapter": log["address"].lower(), "qid": tp[1].lower(),
            "settled_price": _int256(bytes.fromhex(tp[2][2:])),
            "block": int(log["blockNumber"], 16), "ts": int(log["blockTimestamp"], 16)}


def side_of_price(p):
    """Índice de token ganador según la propuesta: 1e18 → 0 (YES/outcome 0); 0 → 1; otro → None."""
    if p == ONE:
        return 0
    if p == 0:
        return 1
    return None


def first_disputes(disputes, qids):
    """Primera disputa (menor (ts, block, log_index)) por questionID de `qids` (iterable)."""
    keep = set(q.lower() for q in qids)
    out = {}
    for d in disputes:
        q = d["qid"].lower()
        if q not in keep:
            continue
        k = (d["ts"], d["block"], d["log_index"])
        if q not in out or k < (out[q]["ts"], out[q]["block"], out[q]["log_index"]):
            out[q] = d
    return out


# ---------------------------------------------------------------- señal y PnL


def entry(trades, idx, t_dispute, delay=DELAY_S, window=WINDOW_S, max_px=MAX_PX):
    """(precio, motivo). Peor compra taker del token idx en (t, t+window], t = disputa + delay.
    Solo usa trades con timestamp en esa ventana (anti-lookahead); None si no hay o si > max_px."""
    t0 = int(t_dispute) + delay
    px = h005.exec_price(trades, idx, t0, t0 + window)
    if px is None:
        return None, "sin_trade"
    if px > max_px:
        return None, "px>max"
    return px, "ok"


def pnl(idx, px, rate, y):
    return h004.pnl(idx, px, rate, y)


# ---------------------------------------------------------------- RPC con caché


def rpc(method, params, tries=8):
    last = None
    for i in range(tries):
        url = RPC[i % len(RPC)]
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=120)
            d = r.json()
            if "result" in d:
                return d["result"]
            last = d.get("error")
        except (requests.RequestException, ValueError) as e:
            last = str(e)
        time.sleep(min(2 ** i, 30))
    raise RuntimeError(f"rpc {method} falló: {last}")


def get_logs(address, topics, a, b, cache_dir, tag, max_logs=5000):
    """eth_getLogs en [a, b] con caché; parte el rango si hay muchos resultados o error."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{tag}_{a}_{b}.json")
    if os.path.exists(path):
        return json.load(open(path))
    try:
        res = rpc("eth_getLogs", [{"fromBlock": hex(a), "toBlock": hex(b), "address": address, "topics": topics}], tries=4)
        if len(res) >= max_logs:
            raise RuntimeError("demasiados logs")
    except RuntimeError:
        if b - a < 1000:
            raise
        m = (a + b) // 2
        res = get_logs(address, topics, a, m, cache_dir, tag) + get_logs(address, topics, m + 1, b, cache_dir, tag)
    json.dump(res, open(path + ".tmp", "w"))
    os.replace(path + ".tmp", path)
    return res


def block_at(ts):
    """Primer bloque con timestamp ≥ ts (búsqueda binaria)."""
    lo, hi = 1, int(rpc("eth_blockNumber", []), 16)
    while lo < hi:
        m = (lo + hi) // 2
        if int(rpc("eth_getBlockByNumber", [hex(m), False])["timestamp"], 16) < ts:
            lo = m + 1
        else:
            hi = m
    return lo
