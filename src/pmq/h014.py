"""H014: mercados de temperatura máxima diaria vs pronóstico Open-Meteo (funciones puras).

Protocolo G0 en HYPOTHESES.md (### H014). Sustituciones documentadas en reports/h014_g1.md:
- `previous_day1` de Open-Meteo = valor predicho 24 h antes de cada HORA válida. Para las horas del
  día objetivo posteriores a t+24h−LAG esa predicción se emitió DESPUÉS de t (lookahead). Por hora se
  usa el menor lead k∈{1,2,3} cuya emisión (h − 24k h) más un retraso de publicación LAG = 6 h sea ≤ t.
- Los tramos se tratan como intervalos continuos según su semántica de redondeo al entero:
  "N" → [N−.5, N+.5); "a-b" (°F) → [a−.5, b+.5); "N o más" → [N−.5, ∞); "N o menos" → (−∞, N+.5).
  Todo se convierte a °C.
- El modelo de error normal (media, sd de observado − pronóstico) se estima por máxima verosimilitud
  con censura por intervalos (el observado solo se conoce como tramo, y los tramos extremos son abiertos).
"""
import math
import re
from datetime import datetime, timedelta, timezone

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

THETA = 0.05          # umbral pre-registrado: prob − precio − comisión ≥ 0.05
LAG_H = 6             # retraso supuesto de publicación de una pasada del modelo (h), pesimista
MIN_FIT = 10          # mínimo de eventos por ciudad para estimar media y sd (si no, no se opera)

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"])}

_NUM = r"(-?\d+(?:\.\d+)?)"
_Q = re.compile(
    r"^Will the highest temperature in (?P<city>.+?)\s+(?:be\s+)*(?:be\s?tween\s+)?"
    r"(?P<a>-?\d+(?:\.\d+)?)\s*(?:[-–]\s*(?P<b>-?\d+(?:\.\d+)?))?\s*°\s*(?P<unit>[CF])"
    r"(?:\s+or\s+(?P<tail>higher|above|below|lower))?\s+on\s+(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2})\??\s*$")

CITY_ALIAS = {"NYC": "New York City"}


def parse_question(q):
    """Devuelve dict(city, unit, kind, lo, hi, month, day) o None. lo/hi en la unidad del mercado."""
    if not isinstance(q, str):
        return None
    m = _Q.match(q.strip())
    if not m:
        return None
    city = re.sub(r"\s+be$", "", m["city"].strip())
    city = CITY_ALIAS.get(city, city)
    month = MONTHS.get(m["month"].lower())
    if month is None:
        return None
    a = float(m["a"])
    b = float(m["b"]) if m["b"] is not None else None
    tail = m["tail"]
    if b is not None and tail is not None:
        return None
    if b is not None:
        if b < a:
            return None
        kind, lo, hi = "range", a, b
    elif tail in ("higher", "above"):
        kind, lo, hi = "ge", a, math.inf
    elif tail in ("below", "lower"):
        kind, lo, hi = "le", -math.inf, a
    else:
        kind, lo, hi = "exact", a, a
    return {"city": city, "unit": m["unit"], "kind": kind, "lo": lo, "hi": hi,
            "month": month, "day": int(m["day"])}


def f_to_c(x):
    return (x - 32.0) * 5.0 / 9.0


def interval_c(p):
    """Intervalo continuo [a, b) en °C del tramo (semántica de redondeo al entero)."""
    a = p["lo"] - 0.5 if math.isfinite(p["lo"]) else -math.inf
    b = p["hi"] + 0.5 if math.isfinite(p["hi"]) else math.inf
    if p["unit"] == "F":
        a, b = (f_to_c(a) if math.isfinite(a) else a), (f_to_c(b) if math.isfinite(b) else b)
    return a, b


def bucket_prob(fc, mu, sd, a, b):
    """P(T ∈ [a, b)) con T ~ N(fc + mu, sd)."""
    za = -math.inf if a == -math.inf else (a - fc - mu) / sd
    zb = math.inf if b == math.inf else (b - fc - mu) / sd
    return float(norm.cdf(zb) - norm.cdf(za))


def fit_error(lo, hi):
    """MLE de (mu, sd) de un error normal observado solo por intervalos [lo, hi) (pueden ser ±inf).
    lo/hi = extremos del tramo ganador menos el pronóstico."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    fin = np.where(np.isfinite(lo) & np.isfinite(hi), (lo + hi) / 2, np.where(np.isfinite(lo), lo, hi))
    mu0, sd0 = float(np.mean(fin)), max(float(np.std(fin)), 0.5)

    def nll(th):
        mu, sd = th[0], math.exp(th[1])
        p = norm.cdf((hi - mu) / sd) - norm.cdf((lo - mu) / sd)
        return -np.sum(np.log(np.clip(p, 1e-12, 1)))

    r = minimize(nll, [mu0, math.log(sd0)], method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-9, "maxiter": 4000})
    return float(r.x[0]), float(math.exp(r.x[1]))


def lead_for_hour(h_ts, t_ts, lag_h=LAG_H, kmax=3):
    """Menor k (días) tal que la predicción hecha 24k h antes de la hora h estaba publicada en t."""
    for k in range(1, kmax + 1):
        if h_ts - 86400 * k + 3600 * lag_h <= t_ts:
            return k
    return None


def _local_hours(tz, target):
    """Timestamps UTC (enteros, en hora exacta) cuya hora local cae en la fecha `target`."""
    start = datetime(target.year, target.month, target.day, tzinfo=tz).astimezone(timezone.utc)
    ts = int(start.timestamp()) // 3600 * 3600 - 3600
    out = []
    for i in range(30):
        h = ts + 3600 * i
        if datetime.fromtimestamp(h, timezone.utc).astimezone(tz).date() == target:
            out.append(h)
    return out


def daily_max_forecast(hourly, tz, target, t_ts, lag_h=LAG_H):
    """Máximo pronosticado del día local `target` (date) usando solo predicciones publicadas en t.
    hourly: dict {ts_utc(int): {1: v1, 2: v2, 3: v3}}. tz: tzinfo de la ciudad.
    None si falta alguna hora del día local."""
    vals = []
    for h in _local_hours(tz, target):
        k = lead_for_hour(h, t_ts, lag_h)
        row = hourly.get(h)
        v = None if (k is None or row is None) else row.get(k)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        vals.append(v)
    return max(vals) if vals else None


def leads_used(tz, target, t_ts, lag_h=LAG_H):
    """Lista de leads usados por hora (diagnóstico)."""
    return [lead_for_hour(h, t_ts, lag_h) for h in _local_hours(tz, target)]


def decision_time(target):
    """t = 12:00 UTC del día anterior a la fecha objetivo (epoch s)."""
    d = datetime(target.year, target.month, target.day, 12, tzinfo=timezone.utc) - timedelta(days=1)
    return int(d.timestamp())


def fee(px, rate):
    return rate * px * (1 - px)


def decide(prob, px_yes, px_no, rate, theta=THETA):
    """('YES'|'NO'|None, precio, edge neto). Elige el lado con mayor edge; apuesta si edge ≥ theta."""
    best = (None, float("nan"), -math.inf)
    if px_yes is not None and not (isinstance(px_yes, float) and math.isnan(px_yes)):
        e = prob - px_yes - fee(px_yes, rate)
        if e > best[2]:
            best = ("YES", px_yes, e)
    if px_no is not None and not (isinstance(px_no, float) and math.isnan(px_no)):
        e = (1 - prob) - px_no - fee(px_no, rate)
        if e > best[2]:
            best = ("NO", px_no, e)
    return best if best[2] >= theta else (None, float("nan"), best[2])


def pnl(side, px, rate, y, cost_mult=1.0, extra_slip=0.0):
    """PnL por acción. Con cost_mult=2 se duplica la comisión y se suma `extra_slip` al precio."""
    payoff = y if side == "YES" else 1 - y
    q = min(px + extra_slip, 0.999)
    return payoff - q - cost_mult * fee(q, rate)


def target_date(month, day, end_ts):
    """Fecha objetivo: el (month, day) más cercano a endDate."""
    best = None
    for yr in (end_ts.year - 1, end_ts.year, end_ts.year + 1):
        try:
            d = datetime(yr, month, day).date()
        except ValueError:
            continue
        diff = abs((d - end_ts.date()).days)
        if best is None or diff < best[0]:
            best = (diff, d)
    return best[1]


# Estaciones de resolución: (lat, lon, zona horaria IANA). Coordenadas del aeródromo (ICAO) o de la
# estación oficial citada en la descripción del mercado; validadas contra la geocodificación de la
# ciudad en experiments/h014_g1.py (distancia < 60 km).
STATIONS = {
    "EHAM": (52.3086, 4.7639, "Europe/Amsterdam"), "LTAC": (40.1281, 32.9951, "Europe/Istanbul"),
    "KATL": (33.6407, -84.4277, "America/New_York"), "KAUS": (30.1945, -97.6699, "America/Chicago"),
    "ZBAA": (40.0801, 116.5846, "Asia/Shanghai"), "SAEZ": (-34.8222, -58.5358, "America/Argentina/Buenos_Aires"),
    "RKPK": (35.1795, 128.9382, "Asia/Seoul"), "FACT": (-33.9715, 18.6021, "Africa/Johannesburg"),
    "ZUUU": (30.5785, 103.9471, "Asia/Shanghai"), "KORD": (41.9742, -87.9073, "America/Chicago"),
    "ZUCK": (29.7192, 106.6417, "Asia/Shanghai"), "KDAL": (32.8471, -96.8518, "America/Chicago"),
    "KBKF": (39.7017, -104.7516, "America/Denver"), "OMDB": (25.2532, 55.3657, "Asia/Dubai"),
    "EFHK": (60.3172, 24.9633, "Europe/Helsinki"), "VHHH": (22.3080, 113.9185, "Asia/Hong_Kong"),
    "HKO": (22.3022, 114.1742, "Asia/Hong_Kong"), "KHOU": (29.6454, -95.2789, "America/Chicago"),
    "LTFM": (41.2753, 28.7519, "Europe/Istanbul"), "WIHH": (-6.2666, 106.8911, "Asia/Jakarta"),
    "OEJN": (21.6796, 39.1565, "Asia/Riyadh"), "WMKK": (2.7456, 101.7099, "Asia/Kuala_Lumpur"),
    "DNMM": (6.5774, 3.3212, "Africa/Lagos"), "EGLC": (51.5048, 0.0495, "Europe/London"),
    "KLAX": (33.9416, -118.4085, "America/Los_Angeles"), "VILK": (26.7606, 80.8893, "Asia/Kolkata"),
    "LEMD": (40.4983, -3.5676, "Europe/Madrid"), "MMMX": (19.4361, -99.0719, "America/Mexico_City"),
    "KMIA": (25.7959, -80.2870, "America/New_York"), "LIMC": (45.6306, 8.7281, "Europe/Rome"),
    "UUWW": (55.5915, 37.2615, "Europe/Moscow"), "EDDM": (48.3537, 11.7750, "Europe/Berlin"),
    "KLGA": (40.7769, -73.8740, "America/New_York"), "MPMG": (8.9733, -79.5556, "America/Panama"),
    "LFPG": (49.0097, 2.5479, "Europe/Paris"), "KPHX": (33.4342, -112.0116, "America/Phoenix"),
    "KSFO": (37.6213, -122.3790, "America/Los_Angeles"), "SBGR": (-23.4356, -46.4731, "America/Sao_Paulo"),
    "KSEA": (47.4502, -122.3088, "America/Los_Angeles"), "RKSI": (37.4602, 126.4407, "Asia/Seoul"),
    "ZSPD": (31.1443, 121.8083, "Asia/Shanghai"), "ZGSZ": (22.6393, 113.8107, "Asia/Shanghai"),
    "WSSS": (1.3644, 103.9915, "Asia/Singapore"), "RCSS": (25.0694, 121.5525, "Asia/Taipei"),
    "RCTP": (25.0777, 121.2328, "Asia/Taipei"),
    "CWA46692": (25.0377, 121.5149, "Asia/Taipei"), "LLBG": (32.0055, 34.8854, "Asia/Jerusalem"),
    "RJTT": (35.5494, 139.7798, "Asia/Tokyo"), "CYYZ": (43.6777, -79.6248, "America/Toronto"),
    "EPWA": (52.1657, 20.9671, "Europe/Warsaw"), "NZWN": (-41.3272, 174.8053, "Pacific/Auckland"),
    "ZHHH": (30.7838, 114.2081, "Asia/Shanghai"),
}


def station_from_description(desc):
    """Código de la estación de resolución citada en la descripción (o None)."""
    if not isinstance(desc, str):
        return None
    m = re.search(r"wunderground\.com/(?:history/daily/(?:[\w%\-]+/)+|weather/)([A-Z0-9]{4})\b", desc)
    if m:
        return m.group(1)
    m = re.search(r"timeseries\?site=([A-Za-z0-9]{4})\b", desc)
    if m:
        return m.group(1).upper()
    if "Hong Kong Observatory" in desc:
        return "HKO"
    m = re.search(r"cwa\.gov\.tw/\S*?ID=(\d+)", desc)
    if m:
        return "CWA" + m.group(1)
    return None
