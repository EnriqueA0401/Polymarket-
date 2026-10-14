"""H016 — mercados cripto de barrera ("reach/hit/dip X") vs probabilidad de toque por reflexión.

Protocolo (HYPOTHESES.md, fijado 2026-10-14): t = endDate − 3d; mercado abierto en t y barrera
no tocada (Binance 1m High/Low) desde el inicio hasta t; P_toque = 2·Φ(−|ln(X/S_t)|/(σ√τ)),
σ = vol realizada 1m (cierres) de los 7 días previos a t, τ en minutos hasta endDate; entrada =
peor compra taker real en (t−1h, t] del lado con ventaja; edge ≥ 0.05 neto de comisión.
"""
import io, os, re, time, zipfile
from math import log, sqrt
import numpy as np
import pandas as pd
import requests

from pmq import h005
from pmq.h011 import phi, sigma_1m
from pmq.universe import DATA

KDIR = os.path.join(DATA, "klines_hl")
LEAD = pd.Timedelta("3D")
SIGMA_WIN = pd.Timedelta("7D")
ENTRY_WIN = 3600            # segundos: (t − 1h, t]
THETA = 0.05
MIN_COVER = 0.9             # cobertura mínima de velas 1m en la ventana de σ
SYMBOL = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}

# ---------------------------------------------------------------- parsing
_ASSET = {"BTC": re.compile(r"(?i)(?<![a-z])(bitcoin|btc)(?![a-z])"),
          "ETH": re.compile(r"(?i)(?<![a-z])(ethereum|eth)(?![a-z])")}
_VERB = re.compile(r"(?i)\b(reach(es|ed)?|hit(s)?|dip(s|ped)?|fall(s)?|drop(s|ped)?)\b")
_DOWN = re.compile(r"(?i)\b(dip(s|ped)?|fall(s)?|drop(s|ped)?|below|sub|under|less|lower)\b")
# importe: con "$" delante o con sufijo k/K (evita fechas como "May 30" o "2025")
_AMT = re.compile(r"(?i)(\$\s?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?(k\b)?|(?<![\w$.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?(k)\b")


def amounts(q):
    out = []
    for m in _AMT.finditer(q or ""):
        if m.group(1):
            num, dec, k = m.group(2), m.group(3), m.group(4)
        else:
            num, dec, k = m.group(5), m.group(6), m.group(7)
        v = float(num.replace(",", "") + (dec or ""))
        out.append(v * (1000 if k else 1))
    return out


def parse_question(q):
    """(asset, barrier, direction_q) o None. direction_q ∈ {'up','down'} según el texto."""
    q = q or ""
    assets = [a for a, rx in _ASSET.items() if rx.search(q)]
    if len(assets) != 1 or not _VERB.search(q):
        return None
    am = sorted(set(amounts(q)))
    if len(am) != 1 or am[0] <= 0:
        return None
    return assets[0], am[0], ("down" if _DOWN.search(q) else "up")


def desc_direction(d):
    """Dirección según la regla de resolución: 'High' → up, 'Low' → down; None si ambigua/ausente."""
    d = d or ""
    hi, lo = bool(re.search(r"(?i)\bhigh\b", d)), bool(re.search(r"(?i)\blow\b", d))
    if hi and not lo:
        return "up"
    if lo and not hi:
        return "down"
    return None


def source(d):
    d = (d or "").lower()
    if "binance" in d:
        return "binance"
    if "coingecko" in d:
        return "coingecko"
    if "coinbase" in d:
        return "coinbase"
    return "other"


# ---------------------------------------------------------------- modelo
def p_touch(S, X, sigma, tau_min):
    """Reflexión sin deriva: P(máximo/mínimo alcance X en τ minutos) = 2·Φ(−|ln(X/S)|/(σ√τ))."""
    if not (S > 0 and X > 0 and sigma > 0 and tau_min > 0):
        return np.nan
    return float(min(1.0, 2 * phi(-abs(log(X / S)) / (sigma * sqrt(tau_min)))))


def closed_before(k, t):
    """Velas 1m completamente cerradas en t (open_time ≤ t − 1 min)."""
    return k.loc[: t - pd.Timedelta(minutes=1)]


def touched(k, X, direction, a, b):
    """¿Alguna vela con open_time en [a, b) tiene High ≥ X (up) o Low ≤ X (down)?"""
    w = k.loc[a: b - pd.Timedelta(microseconds=1)]
    if direction == "up":
        return bool((w.high >= X).any())
    return bool((w.low <= X).any())


def state_at(k, X, direction, start, t):
    """Información conocida en t: (tocada_antes_de_t, S_t, σ, cobertura). Solo usa velas cerradas en t."""
    past = closed_before(k, t)
    win = past.loc[start:]
    hit = bool((win.high >= X).any()) if direction == "up" else bool((win.low <= X).any())
    if len(past) == 0 or past.index[-1] < t - pd.Timedelta(minutes=6):
        return hit, np.nan, np.nan, 0.0
    S = float(past.close.iloc[-1])
    sw = past.loc[t - SIGMA_WIN:]
    cover = len(sw) / (SIGMA_WIN.total_seconds() / 60)
    sig = sigma_1m(sw.close.values) if cover >= MIN_COVER else np.nan
    return hit, S, sig, cover


def evaluate(X, direction, start, end, closed_time, k, trades, rate, theta=THETA, lead=LEAD):
    """Decisión de H016 para un mercado. Solo usa información ≤ t = end − lead.
    Devuelve dict con motivo de exclusión ('why') o la decisión (side, px, edge)."""
    t = end - lead
    out = {"t": t, "why": None, "fair": np.nan, "S": np.nan, "sigma": np.nan,
           "px_yes": None, "px_no": None, "side": None, "px": np.nan, "edge": np.nan}
    if pd.isna(start) or not (start < t):
        out["why"] = "no_abierto_en_t"
        return out
    if pd.notna(closed_time) and closed_time <= t:
        out["why"] = "cerrado_antes_de_t"
        return out
    hit, S, sig, cover = state_at(k, X, direction, start, t)
    out["S"], out["sigma"] = S, sig
    if hit:
        out["why"] = "tocada_antes_de_t"
        return out
    if not np.isfinite(S) or not np.isfinite(sig):
        out["why"] = "sin_klines"
        return out
    tau = (end - t).total_seconds() / 60
    fy = p_touch(S, X, sig, tau)
    out["fair"] = fy
    ts = int(t.timestamp())
    py = h005.exec_price(trades, 0, ts - ENTRY_WIN, ts)
    pn = h005.exec_price(trades, 1, ts - ENTRY_WIN, ts)
    out["px_yes"], out["px_no"] = py, pn
    if py is None and pn is None:
        out["why"] = "sin_trades"
        return out
    side, px, e = h005.decide(fy, py, pn, rate, theta)
    out["side"], out["px"], out["edge"] = side, px, e
    if side is None:
        out["why"] = "sin_senal"
    return out


def median_buy(trades, idx, t0, t1):
    px = [float(x["price"]) for x in trades or []
          if x["outcomeIndex"] == idx and x["side"] == "BUY" and t0 < x["timestamp"] <= t1]
    return float(np.median(px)) if px else None


# ---------------------------------------------------------------- datos Binance con High/Low
def _get(url):
    r = None
    for i in range(6):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code in (200, 404):
                break
        except requests.RequestException:
            r = None
        time.sleep(2 ** i)
    return r if r is not None and r.status_code == 200 else None


def _read_zip(content):
    z = zipfile.ZipFile(io.BytesIO(content))
    k = pd.read_csv(z.open(z.namelist()[0]), header=None).iloc[:, :5]
    k.columns = ["open_time", "open", "high", "low", "close"]
    k = k[pd.to_numeric(k.open_time, errors="coerce").notna()].astype(float)
    # desde 2025 Binance usa microsegundos
    k["t"] = pd.to_datetime(np.where(k.open_time > 1e14, k.open_time // 1000, k.open_time).astype("int64"),
                            unit="ms", utc=True)
    return k[["t", "open", "high", "low", "close"]]


def load_hl(symbol, a, b):
    """Klines 1m Binance spot (open/high/low/close) entre a y b (Timestamps UTC), por meses en caché."""
    os.makedirs(KDIR, exist_ok=True)
    out = []
    for m in pd.period_range(a.tz_convert(None).to_period("M"), b.tz_convert(None).to_period("M"), freq="M"):
        p = os.path.join(KDIR, f"{symbol}_{m}.parquet")
        if not os.path.exists(p):
            r = _get(f"https://data.binance.vision/data/spot/monthly/klines/{symbol}/1m/{symbol}-1m-{m}.zip")
            if r is None:
                continue
            _read_zip(r.content).to_parquet(p)
        out.append(pd.read_parquet(p))
    if not out:
        return pd.DataFrame(columns=["open", "high", "low", "close"])
    k = pd.concat(out).drop_duplicates("t").set_index("t").sort_index()
    return k.loc[a:b]
