"""H011 — mercados cripto Up/Down vs Binance. Probabilidad justa y datos de klines."""
import io, os, time, zipfile
from math import erf, log, sqrt
import numpy as np
import pandas as pd
import requests

from pmq.universe import DATA

KDIR = os.path.join(DATA, "klines")
WINDOW = {"5m": 5, "15m": 15, "hourly": 60}


def phi(x):
    return 0.5 * (1 + erf(x / sqrt(2)))


def fair_twap(S0, A, S, w, tau, sigma):
    """P(TWAP_ventana ≥ S0). A = media de lo transcurrido, w = fracción transcurrida,
    S = precio actual, tau = minutos restantes, sigma = vol por minuto (log)."""
    E = w * A + (1 - w) * S
    sd = (1 - w) * S * sigma * sqrt(max(tau, 1e-9) / 3)
    if sd <= 0:
        return 1.0 if E >= S0 else 0.0
    return phi((E - S0) / sd)


def fair_candle(S0, S, tau, sigma):
    """P(cierre ≥ apertura) con movimiento browniano geométrico sin deriva."""
    sd = sigma * sqrt(max(tau, 1e-9))
    if sd <= 0:
        return 1.0 if S >= S0 else 0.0
    return phi(log(S / S0) / sd)


def sigma_1m(closes):
    r = np.diff(np.log(np.asarray(closes, float)))
    return float(np.std(r, ddof=1)) if len(r) > 5 else np.nan


def load_klines(symbol, days):
    """Klines 1m de Binance spot (data.binance.vision), indexadas por open_time UTC (ms→ts)."""
    os.makedirs(KDIR, exist_ok=True)
    out = []
    for d in days:
        p = os.path.join(KDIR, f"{symbol}_{d:%Y-%m-%d}.parquet")
        if not os.path.exists(p):
            url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/1m/{symbol}-1m-{d:%Y-%m-%d}.zip"
            r = None
            for i in range(6):
                try:
                    r = requests.get(url, timeout=60)
                    if r.status_code in (200, 404):
                        break
                except requests.RequestException:
                    r = None
                time.sleep(2 ** i)
            if r is None or r.status_code != 200:
                continue
            z = zipfile.ZipFile(io.BytesIO(r.content))
            k = pd.read_csv(z.open(z.namelist()[0]), header=None).iloc[:, :5]
            k.columns = ["open_time", "open", "high", "low", "close"]
            unit = "us" if k.open_time.iloc[0] > 1e14 else "ms"   # desde 2025 Binance usa microsegundos
            k["t"] = pd.to_datetime(k.open_time, unit=unit, utc=True)
            k[["t", "open", "close"]].to_parquet(p)
        out.append(pd.read_parquet(p))
    return pd.concat(out).set_index("t").sort_index() if out else pd.DataFrame()
