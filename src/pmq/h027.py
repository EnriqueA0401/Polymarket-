"""H027: temperatura máxima del MISMO día con observaciones METAR (nowcast). Funciones puras.

Protocolo G0 en HYPOTHESES.md (### H027). Reutiliza el parser, las estaciones y los intervalos de H014.
- t = 15:00 hora local de la estación en el día objetivo; información = observaciones METAR con hora
  ≤ t − 15 min; M = máximo acumulado del día local hasta entonces.
- Las temperaturas se expresan como ENTEROS en la unidad del mercado (como las muestra Wunderground):
  °F → redondeo de tmpf; °C → redondeo de (tmpf − 32)·5/9 (en estaciones no EE. UU. tmpf procede del
  grupo entero °C del METAR, así que el redondeo devuelve ese entero exacto).
- Modelo: distribución empírica por (ciudad, unidad) de R = máximo final − M (enteros ≥ 0 en la práctica).
  P(tramo) = Σ_r P(R = r) · 1[lo ≤ M + r ≤ hi], con [lo, hi] los enteros del tramo.
"""
import math
from collections import Counter
from datetime import datetime, timedelta, timezone

import numpy as np

from pmq import h014

DEC_HOUR = 15          # hora local de decisión (pre-registrada)
INFO_LAG_S = 15 * 60   # solo observaciones con hora ≤ t − 15 min
WINDOW_S = 600         # precio = peor compra taker en (t, t + 10 min]
THETA = h014.THETA     # 0.05
MIN_FIT = h014.MIN_FIT  # mínimo de días por (ciudad, unidad) para estimar la distribución
MIN_AGREE = 0.95       # G1: concordancia mínima METAR vs tramo resuelto por ciudad
# calidad mínima de observaciones (fijada antes de ver resultados)
MIN_HOURS_CUM = 8      # horas locales distintas con observación en [00:00, t − 15 min]
RECENT_S = 2 * 3600    # al menos una observación en [t − 15 min − 2 h, t − 15 min]
MIN_HOURS_DAY = 18     # horas distintas con observación en el día local completo (máximo final)

NO_METAR = {"HKO", "CWA46692"}   # estaciones de resolución sin METAR (Observatorio HK, CWA Taipéi)


def to_unit(tmpf, unit):
    """Entero en la unidad del mercado (redondeo half-up) a partir de tmpf (°F)."""
    x = float(tmpf) if unit == "F" else (float(tmpf) - 32.0) * 5.0 / 9.0
    return int(math.floor(round(x, 6) + 0.5))


def bucket_ints(kind, lo, hi):
    """Enteros [lo, hi] del tramo en la unidad del mercado (±inf en los extremos abiertos)."""
    a = -math.inf if not math.isfinite(lo) else int(lo)
    b = math.inf if not math.isfinite(hi) else int(hi)
    return a, b


def local_day(tz, target):
    """(inicio, fin) epoch UTC del día local `target` (fin exclusivo)."""
    s = datetime(target.year, target.month, target.day, tzinfo=tz)
    e = s + timedelta(days=1)
    return int(s.astimezone(timezone.utc).timestamp()), int(e.astimezone(timezone.utc).timestamp())


def decision_ts(tz, target, hour=DEC_HOUR):
    """t = `hour`:00 hora local del día objetivo (epoch UTC)."""
    return int(datetime(target.year, target.month, target.day, hour, tzinfo=tz).astimezone(timezone.utc).timestamp())


def _sel(ts, vals, a, b):
    """Valores con a ≤ ts ≤ b (ts y vals arrays alineados)."""
    ts, vals = np.asarray(ts), np.asarray(vals)
    k = (ts >= a) & (ts <= b)
    return ts[k], vals[k]


def cum_max(ts, vals, day_start, cutoff):
    """Máximo de las observaciones con day_start ≤ ts ≤ cutoff, o None."""
    _, v = _sel(ts, vals, day_start, cutoff)
    return int(v.max()) if len(v) else None


def n_hours(ts, a, b):
    """Horas UTC distintas con alguna observación en [a, b]."""
    t, _ = _sel(ts, np.zeros(len(ts)), a, b)
    return len(set((t // 3600).tolist()))


def nowcast_state(ts, vals, tz, target):
    """(t, M) con solo observaciones ≤ t − 15 min; M = None si los datos no cumplen la calidad mínima."""
    t = decision_ts(tz, target)
    cut = t - INFO_LAG_S
    d0, _ = local_day(tz, target)
    ts = np.asarray(ts)
    if n_hours(ts, d0, cut) < MIN_HOURS_CUM or not np.any((ts >= cut - RECENT_S) & (ts <= cut)):
        return t, None
    return t, cum_max(ts, vals, d0, cut)


def final_max(ts, vals, tz, target):
    """Máximo del día local completo, o None si hay menos de MIN_HOURS_DAY horas con observación."""
    d0, d1 = local_day(tz, target)
    if n_hours(np.asarray(ts), d0, d1 - 1) < MIN_HOURS_DAY:
        return None
    return cum_max(ts, vals, d0, d1 - 1)


def fit_rise(rises):
    """Distribución empírica {r: prob} de R = máximo final − M."""
    c = Counter(int(r) for r in rises)
    n = sum(c.values())
    return {r: k / n for r, k in sorted(c.items())}


def bucket_prob(M, dist, a, b):
    """P(M + R ∈ [a, b]) (enteros, extremos inclusivos, ±inf permitidos)."""
    return float(sum(p for r, p in dist.items() if a <= M + r <= b))


def decide(prob, px_yes, px_no, rate, theta=THETA):
    """Igual que H014: ('YES'|'NO'|None, precio, edge neto). Apuesta si prob − precio − comisión ≥ θ."""
    return h014.decide(prob, px_yes, px_no, rate, theta)


def portfolio_return(pnl, capital, days):
    """Σpnl / Σ(capital·días) · 365 (lección H024)."""
    pnl, capital, days = map(np.asarray, (pnl, capital, days))
    den = float((capital * days).sum())
    return float(pnl.sum() / den * 365) if den > 0 else float("nan")


def bankroll_return(pnl, capital, t_open, t_close):
    """Rentabilidad anualizada con capital ocioso: banca = máximo capital simultáneo comprometido;
    periodo = desde la primera entrada hasta el último cierre. Σpnl / banca / años."""
    ev = sorted([(a, c) for a, c in zip(t_open, capital)] + [(b, -c) for b, c in zip(t_close, capital)],
                key=lambda x: (x[0], x[1]))
    cur = peak = 0.0
    for _, c in ev:
        cur += c
        peak = max(peak, cur)
    years = (max(t_close) - min(t_open)) / (365 * 86400)
    return float(np.sum(pnl) / peak / years) if peak > 0 and years > 0 else float("nan"), peak
