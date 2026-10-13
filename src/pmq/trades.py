"""Trades taker reales de Data API con caché en disco."""
import gzip, json, os, time
import requests

from pmq.universe import DATA

KEEP = ("side", "outcome", "outcomeIndex", "price", "size", "timestamp")


def fetch(cid, a, b, cache_dir):
    """Trades taker de `cid` con timestamp en [a, b]. None si falla de forma persistente."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{cid}_{a}_{b}.json.gz")
    if os.path.exists(path):
        return json.load(gzip.open(path, "rt"))
    for i in range(6):
        try:
            r = requests.get("https://data-api.polymarket.com/trades",
                             params={"market": cid, "takerOnly": "true", "start": a, "end": b, "limit": 10000}, timeout=60)
            if r.status_code == 200:
                d = [{k: x.get(k) for k in KEEP} for x in r.json()]
                json.dump(d, gzip.open(path, "wt"))
                return d
        except requests.RequestException:
            pass
        time.sleep(2 ** i)
    return None
