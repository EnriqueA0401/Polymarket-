"""H020: deriva de la primera hora tras el primer trade taker de un mercado nuevo.

Protocolo (HYPOTHESES.md, fijado antes de ver datos):
- a0 = primer trade taker del mercado (cualquier token).
- p0 = precio del primer trade del token YES (outcomeIndex 0) en [a0, a0+60min].
  Si hay varios trades YES en ese primer segundo, se usa su VWAP (orden intra-segundo desconocido).
- v = VWAP de trades taker del token YES en [a0+50min, a0+60min].
- deriva = v − p0; señal si |deriva| ≥ 0.05 y v ∈ [0.10, 0.90].
- A (momentum) compra el lado de la deriva; B (reversión) el contrario.
- Entrada = peor compra taker real del token en (a0+60min, a0+120min].
La señal solo usa trades con timestamp ≤ a0+60min; la entrada solo trades posteriores.
"""
import numpy as np

LIMIT = 10000
W_LO, W_HI = 3000, 3600          # ventana de la VWAP (s desde a0)
ENTRY = (3600, 7200)             # ventana de entrada (s desde a0), abierta a la izquierda
MIN_DRIFT, LO, HI = 0.05, 0.10, 0.90
EPS = 1e-9


def fetch_all(fetch, cid, a, b, cap=40):
    """Todos los trades en [a, b] descendiendo cuando la API devuelve el tope de 10,000 (más recientes primero).
    `fetch(cid, a, b)` → lista o None. Devuelve (lista, nº llamadas) o (None, n) si falla o supera `cap`."""
    out, n = [], 0
    while True:
        d = fetch(cid, a, b)
        n += 1
        if d is None:
            return None, n
        if len(d) < LIMIT:
            return out + d, n
        tm = min(x["timestamp"] for x in d)
        if tm <= a or n >= cap:
            return None, n                    # no se puede completar la ventana
        out += [x for x in d if x["timestamp"] > tm]   # el segundo tm se vuelve a pedir entero
        b = tm


def first_trade(fetch, cid, start, close, cap=40):
    """Timestamp del primer trade taker. Busca primero en [0, start+3d]; si está vacío, avanza con
    ventanas que se duplican hasta close+1d. Devuelve (a0 o None, nº llamadas, estado)."""
    a, b, step, calls = 0, start + 3 * 86400, 7 * 86400, 0
    end = close + 86400
    while a <= end:
        if calls >= cap:
            return None, calls, "fallo/tope"
        d, n = fetch_all(fetch, cid, a, b, cap=cap - calls)
        calls += n
        if d is None:
            return None, calls, "fallo/tope"
        if d:
            return min(x["timestamp"] for x in d), calls, "ok"
        a, b, step = b + 1, b + step, step * 2
    return None, calls, "sin trades"


def _yes(trades, t0, t1):
    """Trades del token YES con t0 ≤ ts ≤ t1."""
    return [x for x in trades if x["outcomeIndex"] == 0 and t0 <= x["timestamp"] <= t1]


def _vwap(tr):
    s = sum(float(x["size"]) for x in tr)
    return sum(float(x["price"]) * float(x["size"]) for x in tr) / s if s > 0 else None


def signal(trades, a0):
    """(dir, p0, v, deriva): dir = +1 (deriva al alza), −1 (a la baja) o 0 (sin señal / sin datos).
    Solo usa trades con timestamp ≤ a0+60min."""
    tr = [x for x in trades or [] if x["timestamp"] <= a0 + W_HI]
    y = _yes(tr, a0, a0 + W_HI)
    if not y:
        return 0, None, None, None
    t_first = min(x["timestamp"] for x in y)
    p0 = _vwap([x for x in y if x["timestamp"] == t_first])
    v = _vwap(_yes(tr, a0 + W_LO, a0 + W_HI))
    if p0 is None or v is None:
        return 0, p0, v, None
    d = v - p0
    ok = abs(d) >= MIN_DRIFT - EPS and LO - EPS <= v <= HI + EPS
    return (int(np.sign(d)) if ok else 0), p0, v, d


def side(direction, variant):
    """Token a comprar: 0 = YES, 1 = NO. A sigue la deriva; B la revierte."""
    up = direction > 0 if variant == "A" else direction < 0
    return 0 if up else 1


def entry(trades, idx, a0):
    """(peor precio, mediana) de compras taker del token `idx` en (a0+60min, a0+120min]."""
    px = [float(x["price"]) for x in trades or []
          if x["outcomeIndex"] == idx and x["side"] == "BUY" and a0 + ENTRY[0] < x["timestamp"] <= a0 + ENTRY[1]]
    return (max(px), float(np.median(px))) if px else (None, None)


def cluster_p(df, col="pnl", cluster="event_id"):
    """p unilateral (H1: media > 0) con error estándar robusto por clusters (estimador de razón)."""
    from math import erf, sqrt
    g = df.groupby(cluster)[col].agg(["sum", "count"])
    N, k = g["count"].sum(), len(g)
    m = g["sum"].sum() / N
    se = np.sqrt(((g["sum"] - m * g["count"]) ** 2).sum() * k / (k - 1)) / N
    return float(1 - 0.5 * (1 + erf((m / se) / sqrt(2)))) if se > 0 else float("nan")


def holm(pvals, alpha=0.05):
    """Lista de booleanos (rechazo de H0) con el procedimiento de Holm."""
    order = np.argsort(pvals)
    rej = [False] * len(pvals)
    for r, i in enumerate(order):
        if pvals[i] < alpha / (len(pvals) - r):
            rej[i] = True
        else:
            break
    return rej
