"""Descarga el universo completo de mercados cerrados de Gamma.

Paginación keyset en paralelo por ventanas diarias de endDate (2019-01-01 … 2031-01-01) más
una ventana abierta [2031, ∞). Los mercados sin endDate no son filtrables por esta vía:
se cuentan aparte en la verificación (ver data_manifest.json).
Uso: PYTHONPATH=src python -m pmq.ingest_gamma
Salida: data/gamma/win_YYYY-MM-DD.jsonl.gz (una por ventana; reanudable por ventana).
Volumen observado: ~17-24k mercados cerrados por día en 2026 (sobre todo cripto/deportes).
"""
import gzip, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests

BASE = "https://gamma-api.polymarket.com/markets/keyset"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gamma")
DROP = {"image", "icon", "twitterCardImage"}


def slim(m):
    m = {k: v for k, v in m.items() if k not in DROP}
    for e in m.get("events") or []:
        for k in ("image", "icon", "description", "markets", "series"):
            e.pop(k, None)
    return m


def get(params, tries=7):
    for i in range(tries):
        try:
            r = requests.get(BASE, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            print("http", r.status_code, r.text[:200], file=sys.stderr, flush=True)
        except requests.RequestException as e:
            print("err", e, file=sys.stderr, flush=True)
        time.sleep(2 ** i)
    raise RuntimeError(f"fallo persistente {params}")


def window(a, b, name):
    path = os.path.join(OUT, f"win_{name}.jsonl.gz")
    if os.path.exists(path):
        return 0
    rows, cursor = [], None
    while True:
        p = {"closed": "true", "limit": 100, "end_date_min": a}
        if b:
            p["end_date_max"] = b
        if cursor:
            p["after_cursor"] = cursor
        d = get(p)
        ms = d.get("markets") or []
        rows.extend(slim(m) for m in ms)
        cursor = d.get("next_cursor")
        if not cursor or not ms:
            break
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt") as f:
        for m in rows:
            f.write(json.dumps(m) + "\n")
    os.replace(tmp, path)
    if len(rows) > 50:
        print(f"{name} {len(rows)}", flush=True)
    return len(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    ms = pd.date_range("2019-01-01", "2031-01-01", freq="D", tz="UTC")
    jobs = [(ms[i].strftime("%Y-%m-%dT%H:%M:%SZ"), ms[i + 1].strftime("%Y-%m-%dT%H:%M:%SZ"),
             ms[i].strftime("%Y-%m-%d")) for i in range(len(ms) - 1)]
    jobs.append(("2031-01-01T00:00:00Z", None, "2031plus"))
    jobs.reverse()  # los meses recientes son los más grandes: empezar por ellos
    with ThreadPoolExecutor(8) as ex:
        total = sum(ex.map(lambda j: window(*j), jobs))
    print(f"FIN {total}", flush=True)


if __name__ == "__main__":
    main()
