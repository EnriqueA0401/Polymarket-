"""Descarga el universo completo de mercados cerrados de Gamma (keyset pagination).

Uso: python -m pmq.ingest_gamma   (desde src/, o con PYTHONPATH=src)
Salida: data/gamma/markets_closed_XXXX.jsonl.gz (trozos) + data/gamma/cursor.txt (reanudable).
Se guarda el registro crudo sin imágenes ni descripciones largas truncadas.
"""
import gzip, json, os, sys, time
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


def get(params, tries=6):
    for i in range(tries):
        try:
            r = requests.get(BASE, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            print("http", r.status_code, r.text[:200], file=sys.stderr)
        except requests.RequestException as e:
            print("err", e, file=sys.stderr)
        time.sleep(2 ** i)
    raise RuntimeError("fallo persistente")


def main():
    os.makedirs(OUT, exist_ok=True)
    cpath = os.path.join(OUT, "cursor.txt")
    cursor = open(cpath).read().strip() if os.path.exists(cpath) else None
    if cursor == "DONE":
        print("ya completo"); return
    chunk = len([f for f in os.listdir(OUT) if f.startswith("markets_closed_")])
    buf, n = [], 0
    while True:
        p = {"closed": "true", "limit": 1000}
        if cursor:
            p["after_cursor"] = cursor
        d = get(p)
        ms = d.get("markets") or []
        buf.extend(slim(m) for m in ms)
        n += len(ms)
        cursor = d.get("next_cursor")
        if len(buf) >= 20000 or not cursor or not ms:
            with gzip.open(os.path.join(OUT, f"markets_closed_{chunk:04d}.jsonl.gz"), "wt") as f:
                for m in buf:
                    f.write(json.dumps(m) + "\n")
            chunk += 1; buf = []
            open(cpath, "w").write(cursor or "DONE")
            print(f"{n} mercados, último id {ms[-1]['id'] if ms else '-'}", flush=True)
        if not cursor or not ms:
            break


if __name__ == "__main__":
    main()
