"""H028 — "¿Batirá X sus beneficios trimestrales?" vs historial de batidas de la empresa.

Protocolo G0 (HYPOTHESES.md, fijado 2026-10-14):
- prob = (k + 0.76·4) / (n + 4), k batidas en los últimos n ≤ 8 informes con fecha < t.
- t = 24 h antes de la hora del informe (o de endDate si no consta).
- precio = peor compra taker real en (t − 23 h, t]; señal si prob − precio − comisión ≥ 0.05.
- clusters = fecha del informe.
"""
import os, re, time
import numpy as np
import pandas as pd

PRIOR, PRIOR_W, N_MAX, THETA = 0.76, 4.0, 8, 0.05
LEAD = pd.Timedelta("24h")
WINDOW = pd.Timedelta("23h")
MATCH_DAYS = 20  # tolerancia para emparejar el informe de Yahoo con la fecha estimada del mercado

_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def parse_ticker(question, description=""):
    """Ticker entre paréntesis en la pregunta; si no, '(NASDAQ: XXX)' / '(NYSE: XXX)' en la descripción."""
    m = re.search(r"\(([A-Z][A-Z0-9.\-]{0,6})\)", question or "")
    if m:
        return m.group(1)
    m = re.search(r"\((?:NASDAQ|NYSE|NYSE American|AMEX)\s*:\s*([A-Z][A-Z0-9.\-]{0,6})\)", description or "")
    return m.group(1) if m else None


def parse_strike(description):
    """Umbral de EPS: 'greater than $X' (admite negativos '-$0.12' o '$-0.12')."""
    m = re.search(r"greater than\s*(-)?\s*\$\s*(-)?([0-9]+(?:\.[0-9]+)?)", description or "")
    if not m:
        return None
    v = float(m.group(3))
    return -v if (m.group(1) or m.group(2)) else v


def parse_est_date(description):
    """Fecha estimada del informe ('... earnings on October 9, 2026')."""
    m = re.search(rf"earnings on ((?:{_MONTHS}) \d{{1,2}}, \d{{4}})", description or "")
    if not m:
        return None
    return pd.Timestamp(pd.to_datetime(m.group(1), format="%B %d, %Y")).tz_localize("America/New_York")


def beat_flag(reported, estimate):
    """1 si EPS publicado > consenso (redondeado a céntimos, empate = no batida), NaN si falta alguno."""
    if reported is None or estimate is None or pd.isna(reported) or pd.isna(estimate):
        return np.nan
    return float(round(float(reported), 2) > round(float(estimate), 2))


def base_rate(hist, t, n_max=N_MAX, prior=PRIOR, w=PRIOR_W):
    """(prob, n, k) usando SOLO informes con fecha estrictamente < t y batida conocida.

    hist: DataFrame con columnas 'date' (Timestamp tz-aware) y 'beat' (0/1/NaN).
    """
    if hist is None or len(hist) == 0:
        return prior, 0, 0
    h = hist[(hist["date"] < t) & hist["beat"].notna()].sort_values("date")
    h = h.tail(n_max)
    n, k = len(h), int(h["beat"].sum())
    return (k + prior * w) / (n + w), n, k


def match_report(hist, anchor, tol_days=MATCH_DAYS):
    """Fila de `hist` cuya fecha está más cerca de `anchor` (± tol_days). None si no hay."""
    if hist is None or len(hist) == 0 or anchor is None or pd.isna(anchor):
        return None
    d = (hist["date"] - anchor).abs()
    i = d.idxmin()
    return hist.loc[i] if d.loc[i] <= pd.Timedelta(days=tol_days) else None


def decision_time(report_time, end):
    """t = hora del informe − 24 h (si no consta, endDate − 24 h)."""
    base = report_time if report_time is not None and not pd.isna(report_time) else end
    return base - LEAD


# ---------- Yahoo (yfinance) con caché ----------

def yahoo_history(ticker, cache_dir, limit=40):
    """Historial de informes de Yahoo: date (UTC), estimate, reported, beat. Caché parquet por ticker."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{ticker}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    import yfinance as yf
    sym = ticker.replace(".", "-")
    d = None
    for i in range(4):
        try:
            d = yf.Ticker(sym).get_earnings_dates(limit=limit)
            break
        except Exception as e:  # noqa: BLE001 — red/ratelimit: reintentar
            if "No earnings dates" in str(e) or "delisted" in str(e).lower():
                d = None
                break
            time.sleep(2 ** (i + 1))
    if d is None or len(d) == 0:
        out = pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns, UTC]"),
                            "estimate": [], "reported": [], "beat": []})
    else:
        d = d.reset_index()
        out = pd.DataFrame({"date": pd.to_datetime(d.iloc[:, 0], utc=True),
                            "estimate": d["EPS Estimate"].astype(float).values,
                            "reported": d["Reported EPS"].astype(float).values})
        out["beat"] = [beat_flag(r, e) for r, e in zip(out.reported, out.estimate)]
        out = out.sort_values("date").reset_index(drop=True)
    out.to_parquet(path)
    return out
