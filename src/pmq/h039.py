"""H039 [BIN] — Arbitraje entre plataformas Kalshi ↔ Polymarket (mismo partido, ganador NFL/NBA/MLB).

Protocolo G0 (HYPOTHESES.md, fijado 2026-10-14 antes de ver datos):
  por partido emparejado (tabla de H023) y minuto de reloj antes del inicio con compras taker en ambas
  plataformas: coste = peor compra en Kalshi de la exposición "gana el equipo e" + peor compra en PM del
  token del otro equipo + comisiones de ambas. Oportunidad si coste < 0.99. Variantes: 1.

Orientación (verificada con tests):
  - PM: token outcomeIndex 0 paga si gana team0 (nombre completo de H023), token 1 si gana team1.
  - Kalshi: cada partido tiene dos mercados, "<team0> wins" (k_ticker0) y "<team1> wins".
    Compra YES del mercado del equipo X  ≡ exposición "gana X".
    Compra NO  del mercado del equipo X  ≡ exposición "gana el otro" (precio NO = 1 − yes_price).
  - Par de dirección e ∈ {0, 1}: Kalshi exposición "gana team e" + PM token (1 − e). Paga 1 si ambas
    plataformas resuelven igual (y un equipo gana).
Comisiones:
  - Kalshi taker: ceil_al_céntimo(rate · C · P · (1 − P)) por orden de C contratos. rate = 0.07 (estándar;
    el API de series da fee_multiplier 1 para NBA/NFL y 0.5 para MLB a 2026-10-14 → se usa 1, pesimista).
  - Polymarket taker: rate_mercado · p · (1 − p) por acción (pmq.h001.fee_rate: feeSchedule o 0.07).
"""
import gzip, json, math, os
import numpy as np
import pandas as pd

from pmq import h023 as H
from pmq import trades as T
from pmq.universe import DATA

CACHE = os.path.join(DATA, "h039")
K_RATE = 0.07          # comisión taker Kalshi (multiplicador 1, pesimista)
THRESH = 0.99          # oportunidad si coste por par < THRESH
C_REF = 100            # tamaño de orden de referencia (contratos) para el redondeo de la comisión de Kalshi
LOOKBACK = 14 * 86400  # ventana pre-partido (igual que la caché de Kalshi de H023)


# ---------------------------------------------------------------------------------------------
# Costes
# ---------------------------------------------------------------------------------------------
def k_fee(P, C, rate=K_RATE):
    """Comisión taker de Kalshi (USD) de una orden de C contratos a precio P (USD): redondeo al céntimo
    superior de rate·C·P·(1−P). El round(…, 6) evita que el error de coma flotante sume un céntimo."""
    x = round(rate * C * P * (1 - P) * 100, 6)
    return math.ceil(x) / 100


def pm_fee(p, rate, C=1.0):
    """Comisión taker de Polymarket (USD) por C acciones a precio p."""
    return rate * C * p * (1 - p)


def pair_cost(pk, pp, pm_rate, C=C_REF, k_rate=K_RATE):
    """Coste por par (USD) incluyendo comisiones: Kalshi a pk + PM a pp, orden de C de cada lado."""
    return pk + pp + k_fee(pk, C, k_rate) / C + pm_fee(pp, pm_rate)


def pair_payoff(e, y_pm0, k_team0):
    """Pago de un par de dirección e. y_pm0 = pago del token 0 de PM (1/0/0.5); k_team0 = liquidación del
    mercado de Kalshi del team0 (1/0 o valor escalar si Kalshi anula/fija 'precio justo')."""
    k_leg = k_team0 if e == 0 else 1 - k_team0
    pm_leg = 1 - y_pm0 if e == 0 else y_pm0
    return k_leg + pm_leg


# ---------------------------------------------------------------------------------------------
# Trades → compras por exposición
# ---------------------------------------------------------------------------------------------
def k_buys(trades, team):
    """Compras taker de un mercado de Kalshi del equipo `team` (0/1) → DataFrame t, exp, price, size."""
    rows = []
    for x in trades or []:
        y = float(x["yes_price_dollars"])
        if x["taker_side"] == "yes":
            rows.append((x["created_time"], team, y, float(x["count_fp"])))
        elif x["taker_side"] == "no":
            rows.append((x["created_time"], 1 - team, round(1 - y, 4), float(x["count_fp"])))
    df = pd.DataFrame(rows, columns=["t", "exp", "price", "size"])
    if len(df):
        ts = pd.to_datetime(df.t, utc=True, format="mixed")
        df["t"] = (ts - pd.Timestamp(0, tz="UTC")).dt.total_seconds()     # independiente de la resolución (ns/us)
    return df.astype({"t": float})


def pm_buys(trades):
    """Compras taker de PM → DataFrame t, exp (= outcomeIndex), price, size. Las ventas se ignoran
    (no son compras del token contrario)."""
    rows = [(float(x["timestamp"]), int(x["outcomeIndex"]), float(x["price"]), float(x["size"]))
            for x in trades or [] if x.get("side") == "BUY"]
    return pd.DataFrame(rows, columns=["t", "exp", "price", "size"])


def _worst(df):
    """Por (minuto, exp): peor (máximo) precio, instante de esa compra, tamaño total y tamaño a ese precio."""
    d = df.copy()
    d["minute"] = np.floor(d.t / 60).astype(np.int64)
    d = d.sort_values(["minute", "exp", "price", "t"])
    g = d.groupby(["minute", "exp"])
    out = g.agg(price=("price", "max"), size=("size", "sum"))
    last = g.tail(1).set_index(["minute", "exp"])            # fila de precio máximo (último si empate)
    out["t_worst"] = last.t
    out["size_at_worst"] = d.merge(out.price.rename("pmax"), left_on=["minute", "exp"], right_index=True) \
        .query("price == pmax").groupby(["minute", "exp"])["size"].sum()
    return out.reset_index()


def pairs(kb, pb, gs, pm_rate, C=C_REF, k_rate=K_RATE):
    """Pares (minuto, dirección e) con compras en ambas plataformas antes de gs (inicio, unix s).
    e = exposición del lado de Kalshi; el lado PM es el token 1 − e. Columnas: minute, e, pk, pp, cost,
    profit, k_size, pm_size, k_size_w, pm_size_w, dt (s entre la peor compra de cada lado)."""
    cols = ["minute", "e", "pk", "pp", "cost", "profit", "k_size", "pm_size", "k_size_w", "pm_size_w", "dt"]
    kb = kb[kb.t < gs] if len(kb) else kb
    pb = pb[pb.t < gs] if len(pb) else pb
    if not len(kb) or not len(pb):
        return pd.DataFrame(columns=cols)
    k, p = _worst(kb), _worst(pb)
    p = p.assign(exp=1 - p.exp)                               # PM token 1−e casa con exposición Kalshi e
    m = k.merge(p, on=["minute", "exp"], suffixes=("_k", "_p"))
    if not len(m):
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame({
        "minute": m.minute, "e": m.exp, "pk": m.price_k, "pp": m.price_p,
        "k_size": m.size_k, "pm_size": m.size_p, "k_size_w": m.size_at_worst_k, "pm_size_w": m.size_at_worst_p,
        "dt": (m.t_worst_k - m.t_worst_p).abs()})
    out["cost"] = [pair_cost(a, b, pm_rate, C, k_rate) for a, b in zip(out.pk, out.pp)]
    out["profit"] = 1 - out.cost
    return out[cols].reset_index(drop=True)


# ---------------------------------------------------------------------------------------------
# Descargas (cachés propias en data/h039; la caché de H023 se lee pero no se escribe)
# ---------------------------------------------------------------------------------------------
def _gz_load(path):
    try:
        return json.load(gzip.open(path, "rt"))
    except (OSError, EOFError, ValueError):
        return None


def k_trades(ticker, a, b):
    """Trades de Kalshi en [a, b]: primero la caché de H023 (misma clave), si no API → data/h039/ktrades."""
    h = os.path.join(H.CACHE, "ktrades", f"{ticker}_{a}_{b}.json.gz")
    if os.path.exists(h):
        d = _gz_load(h)
        if d is not None:
            return d
    d0 = os.path.join(CACHE, "ktrades")
    os.makedirs(d0, exist_ok=True)
    path = os.path.join(d0, f"{ticker}_{a}_{b}.json.gz")
    if os.path.exists(path):
        d = _gz_load(path)
        if d is not None:
            return d
    out, cur = [], None
    while True:
        q = {"ticker": ticker, "min_ts": int(a), "max_ts": int(b), "limit": 1000}
        if cur:
            q["cursor"] = cur
        r = H.k_get("/historical/trades", q)
        if r is None:
            break
        out += [{k: x.get(k) for k in H.K_KEEP} for x in r.get("trades", [])]
        cur = r.get("cursor")
        if not cur or not r.get("trades"):
            break
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt") as f:
        json.dump(out, f)
    os.replace(tmp, path)
    return out


def pm_trades(cid, a, b):
    """Trades taker de PM en [a, b]; parte la ventana si llega al límite de 10,000 filas."""
    d = T.fetch(cid, a, b, os.path.join(CACHE, "pmtrades"))
    if d is not None and len(d) >= 10000 and b - a > 60:
        mid = (a + b) // 2
        x, y = pm_trades(cid, a, mid), pm_trades(cid, mid + 1, b)
        d = None if x is None or y is None else x + y
    return d


# ---------------------------------------------------------------------------------------------
# Libros (registro forward)
# ---------------------------------------------------------------------------------------------
def k_asks(book_fp, side):
    """Asks para comprar `side` ('yes'/'no') de un mercado de Kalshi a partir de orderbook_fp, que solo trae
    bids: el ask de YES a precio 1 − q sale de un bid de NO a q (y viceversa). Lista (precio, tamaño) asc."""
    other = (book_fp or {}).get("no_dollars" if side == "yes" else "yes_dollars") or []
    return sorted((round(1 - float(p), 4), float(s)) for p, s in other)


def k_buy_cost(asks, C, rate=K_RATE):
    """Coste total (USD) de comprar C contratos barriendo `asks`, con comisión por nivel redondeada al
    céntimo superior (pesimista: cada nivel como orden separada). NaN si no hay profundidad."""
    left, cost = C, 0.0
    for px, sz in asks:
        take = min(sz, left)
        if take <= 0:
            continue
        cost += take * px + k_fee(px, take, rate)
        left -= take
        if left <= 1e-9:
            return cost
    return np.nan
