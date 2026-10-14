"""H038 [BIN] — Calibración en Kalshi con precios ejecutables (favorito-longshot).

Protocolo G0 (HYPOTHESES.md, fijado antes de ver datos de Kalshi):
  universo = mercados binarios liquidados de Kalshi; entrenamiento = liquidados < 2026-04-12;
  t = cierre programado − 24 h; P_yes = último trade ≤ t; señal P_yes ≤ 0.10 → comprar NO,
  P_yes ≥ 0.90 → comprar YES; precio ejecutable = PEOR compra taker real del lado elegido en
  (t − 1 h, t]; comisión taker de Kalshi ceil(0.07·m·C·P·(1−P)) céntimos por orden.

Decisiones de implementación (fijadas antes de ver resultados; documentadas en reports/h038_g*.md):
  - Cierre programado = expected_expiration_time si existe; si no, close_time. close_time se
    reescribe con el cierre real cuando el mercado cierra antes (can_close_early), así que no es
    "conocido de antemano"; expected_expiration_time es la hora prevista fijada al listar.
  - Lado del taker = taker_outcome_side (buy-yes/sell-no → 'yes'; buy-no/sell-yes → 'no'); si falta,
    taker_side (legado). Se excluyen block trades (no son ejecutables contra el libro).
  - Precio del lado NO = no_price = 1 − yes_price.
  - Tamaño de orden C = 100 contratos (≈ 90–100 USD con capital < 1.000 USD); la comisión se redondea
    al céntimo por orden (miembro no directo), como en el cuadro general de Kalshi.
  - Mercados anulados (result ∉ {yes, no}): se devuelve el precio pagado; se pierde la comisión.
  - Multiplicador de comisión = el vigente de la serie (/series fee_multiplier); si falta, 1.
"""
import gzip, hashlib, json, math, os, threading, time
import numpy as np
import pandas as pd
import requests

from pmq.universe import DATA

K_API = "https://api.elections.kalshi.com/trade-api/v2"
CACHE = os.path.join(DATA, "h038")
HOLDOUT_START = pd.Timestamp("2026-04-12", tz="UTC")
HORIZON = 24 * 3600            # t = cierre programado − 24 h
WINDOW = 3600                  # ventana de ejecución (t − 1 h, t]
LO, HI = 0.10, 0.90            # umbrales de la señal (únicos; 1 variante)
ORDER_C = 100                  # contratos por orden
FEE_RATE = 0.07                # cuadro general de Kalshi (taker)


# ---------------------------------------------------------------------------------------------
# Comisiones y PnL
# ---------------------------------------------------------------------------------------------
def kalshi_fee(c, p, mult=1.0, rate=FEE_RATE):
    """Comisión taker en USD de UNA orden de c contratos a precio p (USD): ceil al céntimo de
    rate·mult·c·p·(1−p). El round(…, 6) evita que 0.07·100·0.5·0.5·100 = 175.00000000000003 suba un
    céntimo por error de coma flotante."""
    x = rate * mult * c * p * (1 - p) * 100.0
    return math.ceil(round(x, 6)) / 100.0


def pnl_per_contract(side, price, result, c=ORDER_C, mult=1.0, fee_mult=1.0, extra_slip=0.0):
    """PnL por contrato (USD) de comprar `side` a `price` y mantener hasta liquidación.
    fee_mult escala la comisión (costes ×2); extra_slip empeora el precio pagado."""
    q = min(price + extra_slip, 0.99)
    fee = fee_mult * kalshi_fee(c, q, mult) / c
    if result not in ("yes", "no"):          # anulado: se devuelve el coste, se pierde la comisión
        return -fee
    payout = 1.0 if side == result else 0.0
    return payout - q - fee


# ---------------------------------------------------------------------------------------------
# Señal y ejecución (sin lookahead: solo trades con ts ≤ t)
# ---------------------------------------------------------------------------------------------
def norm_trades(raw):
    """Lista de trades crudos de Kalshi → DataFrame (ts, yes, side, count) ordenado, sin block trades."""
    rows = []
    for x in raw:
        if x.get("is_block_trade"):
            continue
        side = x.get("taker_outcome_side") or x.get("taker_side")
        yp = x.get("yes_price_dollars")
        if yp is None and x.get("yes_price") is not None:
            yp = float(x["yes_price"]) / 100.0
        if side not in ("yes", "no") or yp is None:
            continue
        rows.append((x["created_time"], float(yp), side, float(x.get("count_fp") or x.get("count") or 0)))
    df = pd.DataFrame(rows, columns=["created_time", "yes", "side", "count"])
    df["ts"] = pd.to_datetime(df.created_time, utc=True, format="mixed").astype("int64") / 1e9 if len(df) else []
    return df.sort_values("ts", kind="stable").reset_index(drop=True)


def decide(tr, t, lo=LO, hi=HI, window=WINDOW):
    """Decisión en t a partir de trades normalizados. Devuelve dict con p_yes (último trade ≤ t),
    side ('yes'/'no'/None), exec_price (peor compra taker del lado en (t−window, t]) y n/volumen del
    lado en la ventana. Solo mira trades con ts ≤ t."""
    out = dict(p_yes=np.nan, p_age=np.nan, side=None, exec_price=np.nan, ref_price=np.nan,
               n_side=0, vol_side=0.0, n_win=0)
    past = tr[tr.ts <= t]
    if not len(past):
        return out
    last = past.iloc[-1]
    out["p_yes"], out["p_age"] = float(last.yes), float(t - last.ts)
    win = past[past.ts > t - window]
    out["n_win"] = int(len(win))
    if out["p_yes"] <= lo:
        side = "no"
    elif out["p_yes"] >= hi:
        side = "yes"
    else:
        return out
    out["side"] = side
    out["ref_price"] = out["p_yes"] if side == "yes" else 1.0 - out["p_yes"]
    w = win[win.side == side]
    out["n_side"], out["vol_side"] = int(len(w)), float(w["count"].sum())
    if len(w):
        px = w.yes if side == "yes" else 1.0 - w.yes
        out["exec_price"] = float(round(px.max(), 6))
    return out


def schedule_ref(m):
    """Cierre programado conocido de antemano: expected_expiration_time, si no close_time."""
    s = m.get("expected_expiration_time") or m.get("close_time")
    return pd.Timestamp(s).tz_convert("UTC") if s else pd.NaT


# ---------------------------------------------------------------------------------------------
# Muestreo por evento (hash fijo)
# ---------------------------------------------------------------------------------------------
def ev_hash(event_ticker):
    """Valor uniforme en [0,1) determinista por evento (sha256)."""
    return int(hashlib.sha256(event_ticker.encode()).hexdigest()[:12], 16) / 16 ** 12


# ---------------------------------------------------------------------------------------------
# API de Kalshi (pública, sin autenticación) con límite de ritmo global y caché
# ---------------------------------------------------------------------------------------------
_last = [0.0]
_lock = threading.Lock()
MIN_GAP = 0.075


def k_get(path, params, tries=12):
    for i in range(tries):
        with _lock:
            dt = time.time() - _last[0]
            if dt < MIN_GAP:
                time.sleep(MIN_GAP - dt)
            _last[0] = time.time()
        try:
            r = requests.get(K_API + path, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
            if r.status_code == 400:
                raise RuntimeError(f"400 {path} {params} {r.text[:200]}")
        except requests.RequestException:
            pass
        time.sleep(min(30, 0.5 * 2 ** i))
    raise RuntimeError(f"Kalshi {path} {params} falló")


def _dump(obj, path):
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def _load(path):
    try:
        with gzip.open(path, "rt") as f:
            return json.load(f)
    except (OSError, EOFError, ValueError):
        return None


M_KEEP = ("ticker", "event_ticker", "market_type", "status", "result", "open_time", "close_time",
          "expected_expiration_time", "settlement_ts", "volume_fp", "can_close_early", "title")


def event_markets(event_ticker):
    """Mercados históricos (archivados) del evento, SOLO los de entrenamiento (liquidados antes del
    holdout). Los de holdout se descartan sin guardarse; se devuelve su número. Caché."""
    d = os.path.join(CACHE, "ev")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{event_ticker}.json.gz")
    c = _load(path) if os.path.exists(path) else None
    if c is not None:
        return c
    out, n_hold, cur = [], 0, None
    while True:
        q = {"event_ticker": event_ticker, "limit": 1000}
        if cur:
            q["cursor"] = cur
        r = k_get("/historical/markets", q) or {}
        for m in r.get("markets", []):
            st = m.get("settlement_ts") or m.get("close_time")
            if not st or pd.Timestamp(st) >= HOLDOUT_START:
                n_hold += 1
                continue
            out.append({k: m.get(k) for k in M_KEEP})
        cur = r.get("cursor")
        if not cur or not r.get("markets"):
            break
    res = {"markets": out, "n_holdout_dropped": n_hold}
    _dump(res, path)
    return res


T_KEEP = ("created_time", "yes_price_dollars", "count_fp", "taker_outcome_side", "taker_side",
          "is_block_trade")


def market_trades(ticker, t):
    """Trades de (t − WINDOW, t] (paginados) y, si la ventana está vacía, el último trade ≤ t − WINDOW
    (solo para la tabla de calibración). Nunca se pide nada posterior a t. Caché por ticker."""
    d = os.path.join(CACHE, "tr")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{ticker}_{int(t)}.json.gz")
    c = _load(path) if os.path.exists(path) else None
    if c is not None:
        return c
    out, cur = [], None
    while True:
        q = {"ticker": ticker, "min_ts": int(t - WINDOW), "max_ts": int(t), "limit": 1000}
        if cur:
            q["cursor"] = cur
        r = k_get("/historical/trades", q) or {}
        out += [{k: x.get(k) for k in T_KEEP} for x in r.get("trades", [])]
        cur = r.get("cursor")
        if not cur or not r.get("trades"):
            break
    prev = []
    if not out:
        r = k_get("/historical/trades", {"ticker": ticker, "max_ts": int(t - WINDOW), "limit": 1}) or {}
        prev = [{k: x.get(k) for k in T_KEEP} for x in r.get("trades", [])[:1]]
    res = {"window": out, "prev": prev}
    _dump(res, path)
    return res


def market_obs(m, raw):
    """Observación de un mercado en t: une metadatos + decide() sobre los trades cacheados."""
    tr = norm_trades(raw["window"] + raw["prev"])
    t = m["t"]
    tr = tr[tr.ts <= t]          # cinturón y tirantes: nada posterior a t
    return decide(tr, t)
