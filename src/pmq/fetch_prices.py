"""Descarga historial horario CLOB del token YES en la ventana [end-8d, min(end, closed)].

Solo mercados que existían en end-24h y no cerraron antes de end-7d (necesario para H001).
Reanudable: guarda trozos data/prices/h001_XXXX.jsonl.gz con {"id", "history"}.
Uso: PYTHONPATH=src python -m pmq.fetch_prices
"""
import glob, gzip, hashlib, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests

from pmq.universe import DATA

URL = "https://clob.polymarket.com/prices-history"
OUT = os.path.join(DATA, "prices")
S = requests.Session()


def targets(u):
    d24 = pd.Timedelta("24h"); d7 = pd.Timedelta("7d")
    m = u.enable_ob & u.end.notna() & u.start.notna()
    m &= u.start < (u.end - d24)
    m &= u.closed_time.isna() | (u.closed_time > u.end - d7)
    return u[m]


HOLDOUT_START = pd.Timestamp("2026-04-12", tz="UTC")
K_TRAIN, K_HOLDOUT = 150, 20  # por mil eventos; fijado por presupuesto (~110k mercados), sin ver precios


def in_sample(event_id, k):
    h = int(hashlib.sha256(str(event_id).encode()).hexdigest(), 16) % 1000
    return h < k


def sample(t):
    ho = t.closed_time >= HOLDOUT_START
    k = ho.map({True: K_HOLDOUT, False: K_TRAIN})
    keep = [in_sample(e, kk) for e, kk in zip(t.event_id, k)]
    return t[keep]


def fetch(row):
    end = row.end
    if pd.notna(row.closed_time) and row.closed_time < end:
        end = row.closed_time
    a = int((row.end - pd.Timedelta("8d")).timestamp()) - 3600
    b = int(end.timestamp())
    for i in range(6):
        try:
            r = S.get(URL, params={"market": row.token_yes, "startTs": a, "endTs": b, "fidelity": 60}, timeout=30)
            if r.status_code == 200:
                return {"id": int(row.id), "history": r.json().get("history", [])}
            if r.status_code in (400, 404):
                return {"id": int(row.id), "history": [], "err": r.text[:200]}
        except requests.RequestException:
            pass
        time.sleep(2 ** i)
    return {"id": int(row.id), "history": None, "err": "fallo persistente"}


def main():
    os.makedirs(OUT, exist_ok=True)
    u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"))
    t = sample(targets(u))
    done = set()
    for f in glob.glob(os.path.join(OUT, "h001_*.jsonl.gz")):
        with gzip.open(f, "rt") as fh:
            done.update(json.loads(l)["id"] for l in fh)
    t = t[~t.id.isin(done)]
    print(f"objetivo {len(t)} pendientes (ya {len(done)})", flush=True)
    chunk = len(glob.glob(os.path.join(OUT, "h001_*.jsonl.gz")))
    rows = list(t.itertuples())
    with ThreadPoolExecutor(8) as ex:
        for i in range(0, len(rows), 5000):
            res = list(ex.map(fetch, rows[i:i + 5000]))
            with gzip.open(os.path.join(OUT, f"h001_{chunk:04d}.jsonl.gz"), "wt") as f:
                for r in res:
                    f.write(json.dumps(r) + "\n")
            chunk += 1
            print(f"{i + len(res)}/{len(rows)} fallos={sum(r['history'] is None for r in res)}", flush=True)


if __name__ == "__main__":
    main()
