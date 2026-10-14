"""H032: recuento de posts semanales (Musk, Trump, Zelenskyy…) con el contador de XTracker.

Protocolo pre-registrado (HYPOTHESES.md ### H032):
- t = inicio de la ventana + 4 días. Información: posts con importedAt ≤ t.
- C = posts con createdAt en [inicio, t] e importedAt ≤ t.
- Resto: distribución empírica del número de posts en periodos de duración R = fin − t, tomada de
  las 8 ventanas contiguas no solapadas [t − kR, t − (k−1)R), k = 1..8, contando solo posts con
  importedAt ≤ t.
- P(tramo) = P(C + resto ∈ tramo). Señal prob − precio − comisión ≥ 0.05 (YES o NO de cada tramo).

Todas las marcas de tiempo internas son segundos Unix (int), UTC.
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

from pmq import h005

ET = ZoneInfo("America/New_York")
DEC_OFFSET_S = 4 * 86400          # t = inicio + 4 días
N_WIN = 8                         # ventanas históricas
THETA = 0.05
PRICE_WINDOW_S = 1800             # precio: peor compra taker en (t, t + 30 min]
WEEK_S = 7 * 86400

# serie de Polymarket → handle de XTracker (solo ventanas semanales; se verifica el handle en la descripción)
SERIES_HANDLE = {
    "elon-tweets": "elonmusk",
    "trump-truth-social": "realDonaldTrump",
    "whitehouse-daily-tweets": "WhiteHouse",
    "andrew-tate-tweets": "Cobratate",
    "ted-cruz-daily-tweets": "tedcruz",
    "khamenei-daily-tweets": "khamenei_ir",
    "cz-tweets": "cz_binance",
    "nycmayor-tweets": "NYCMayor",
    "zelenskyy-tweets": "ZelenskyyUa",
}

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"], 1)}

# ---------------------------------------------------------------- tramos


def parse_bucket(title):
    """Tramo inclusivo (lo, hi) de enteros; hi = None si es abierto por arriba.

    Acepta '<20', '20-39', '580+', '≥580', 'less than 40', '40 or more', '19 or fewer', '0-19'.
    Devuelve None si no se reconoce.
    """
    if title is None:
        return None
    s = str(title).strip().lower().replace(",", "").replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s)
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return (lo, hi) if lo <= hi else None
    m = re.fullmatch(r"(?:<|less than |fewer than |under )(\d+)", s)
    if m:
        n = int(m.group(1))
        return (0, n - 1) if n > 0 else None
    m = re.fullmatch(r"(?:<=|≤)\s*(\d+)|(\d+) or (?:fewer|less)", s)
    if m:
        return (0, int(m.group(1) or m.group(2)))
    m = re.fullmatch(r"(\d+)\s*\+|(?:>=|≥)\s*(\d+)|(\d+) or more", s)
    if m:
        return (int(m.group(1) or m.group(2) or m.group(3)), None)
    m = re.fullmatch(r"(?:>|more than |over )(\d+)", s)
    if m:
        return (int(m.group(1)) + 1, None)
    return None


def in_bucket(n, lo, hi):
    n = np.asarray(n)
    return (n >= lo) & ((n <= hi) if hi is not None else True)


def buckets_partition(buckets):
    """True si los tramos (lo, hi) cubren 0..∞ sin huecos ni solapes."""
    b = sorted(buckets, key=lambda x: x[0])
    if not b or b[0][0] != 0:
        return False
    for (l1, h1), (l2, _) in zip(b, b[1:]):
        if h1 is None or l2 != h1 + 1:
            return False
    return b[-1][1] is None


# ---------------------------------------------------------------- ventana


def _et_ts(month, day, year, hh, mm, ampm):
    h = int(hh) % 12 + (12 if ampm.upper() == "PM" else 0)
    return int(datetime(year, month, day, h, int(mm or 0), tzinfo=ET).timestamp())


_TIME = r"(\d{1,2})(?::(\d{2}))?\s*([AP]M)\s*ET"
_PAT = [
    # "from November 25 12:00 PM ET to December 2, 2025 12:00 PM ET"
    re.compile(r"from (\w+) (\d{1,2}),? (?:(\d{4}),? )?" + _TIME + r" to (\w+) (\d{1,2}),? (\d{4}),? " + _TIME),
    # "between March 27, 12:00 PM ET and April 3, 2026, 12:00 PM ET"
    re.compile(r"between (\w+) (\d{1,2}),? (?:(\d{4}),? )?" + _TIME + r" and (\w+) (\d{1,2}),? (\d{4}),? " + _TIME),
]


def parse_window(desc):
    """(inicio, fin) en segundos Unix desde la descripción (horas en ET). None si no se reconoce.

    Si la fecha inicial no lleva año se toma el del final (el anterior si el mes inicial es posterior)."""
    if not desc:
        return None
    for p in _PAT:
        m = p.search(desc)
        if not m:
            continue
        g = m.groups()
        m1, d1, y1, h1, mi1, ap1 = MONTHS.get(g[0].lower()), int(g[1]), g[2], g[3], g[4], g[5]
        m2, d2, y2, h2, mi2, ap2 = MONTHS.get(g[6].lower()), int(g[7]), int(g[8]), g[9], g[10], g[11]
        if m1 is None or m2 is None:
            return None
        y1 = int(y1) if y1 else (y2 - 1 if m1 > m2 else y2)
        return _et_ts(m1, d1, y1, h1, mi1, ap1), _et_ts(m2, d2, y2, h2, mi2, ap2)
    return None


def decision_time(start):
    return int(start) + DEC_OFFSET_S


# ---------------------------------------------------------------- recuentos (sin lookahead)


def count_known(created, imported, a, b, t):
    """Posts con createdAt en [a, b) conocidos en t (importedAt ≤ t). created/imported: arrays en s."""
    created, imported = np.asarray(created), np.asarray(imported)
    return int(((created >= a) & (created < b) & (imported <= t)).sum())


def current_count(created, imported, start, t):
    """C: posts de la ventana hasta t (createdAt ∈ [start, t]) con importedAt ≤ t."""
    created, imported = np.asarray(created), np.asarray(imported)
    return int(((created >= start) & (created <= t) & (imported <= t)).sum())


def remaining_samples(created, imported, t, R, k=N_WIN):
    """Recuentos en las k ventanas contiguas [t − jR, t − (j−1)R), j = 1..k, con importedAt ≤ t."""
    return np.array([count_known(created, imported, t - j * R, t - (j - 1) * R, t) for j in range(1, k + 1)])


def history_ok(first_imported, first_created, start, t, R, k=N_WIN):
    """El tracker ya funcionaba al empezar la ventana y hay ≥ k·R de historial antes de t."""
    return first_imported <= start and first_created <= t - k * R


def bucket_prob(C, samples, lo, hi):
    """P(C + resto ∈ [lo, hi]) con la distribución empírica de `samples`."""
    s = np.asarray(samples)
    return float(in_bucket(C + s, lo, hi).mean())


def final_count(created, start, end):
    """Recuento final de la ventana [start, end) (para G1/resolución; no se usa como feature)."""
    created = np.asarray(created)
    return int(((created >= start) & (created < end)).sum())


def decide(prob, px_yes, px_no, rate, theta=THETA):
    return h005.decide(prob, px_yes, px_no, rate, theta)
