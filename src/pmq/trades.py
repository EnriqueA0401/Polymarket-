"""Trades taker reales de Data API con caché en disco."""
import gzip, json, os, time
import requests


def _load(path):
    """Lee caché; None si no existe o está corrupta (escritura interrumpida)."""
    if not os.path.exists(path):
        return None
    try:
        return json.load(gzip.open(path, "rt"))
    except (OSError, EOFError, ValueError):
        os.remove(path)
        return None


def _save(path, d):
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt") as f:
        json.dump(d, f)
    os.replace(tmp, path)

from pmq.universe import DATA

KEEP = ("side", "outcome", "outcomeIndex", "price", "size", "timestamp")


def fetch(cid, a, b, cache_dir):
    """Trades taker de `cid` con timestamp en [a, b]. None si falla de forma persistente."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{cid}_{a}_{b}.json.gz")
    c = _load(path)
    if c is not None:
        return c
    for i in range(6):
        try:
            r = requests.get("https://data-api.polymarket.com/trades",
                             params={"market": cid, "takerOnly": "true", "start": a, "end": b, "limit": 10000}, timeout=60)
            if r.status_code == 200:
                d = [{k: x.get(k) for k in KEEP} for x in r.json()]
                _save(path, d)
                return d
        except requests.RequestException:
            pass
        time.sleep(2 ** i)
    return None


FULL = ("proxyWallet", "side", "asset", "conditionId", "outcomeIndex", "price", "size", "timestamp")


def _get(params, tries=6):
    for i in range(tries):
        try:
            r = requests.get("https://data-api.polymarket.com/trades", params=params, timeout=60)
            if r.status_code == 200:
                return [{k: x.get(k) for k in FULL} for x in r.json()]
        except requests.RequestException:
            pass
        time.sleep(2 ** i)
    return None


def fetch_market_full(cid, cache_dir):
    """Hasta 10,000 trades taker más recientes del mercado, con wallet."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{cid}.json.gz")
    c = _load(path)
    if c is not None:
        return c
    d = _get({"market": cid, "takerOnly": "true", "limit": 10000})
    if d is not None:
        _save(path, d)
    return d


def fetch_user(user, a, b, cache_dir):
    """Todos los trades taker de una wallet en [a, b]; parte la ventana si llega al límite."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{user}_{a}_{b}.json.gz")
    c = _load(path)
    if c is not None:
        return c
    d = _get({"user": user, "takerOnly": "true", "start": a, "end": b, "limit": 10000})
    if d is None:
        return None
    if len(d) >= 10000 and b - a > 3600:
        mid = (a + b) // 2
        x, y = fetch_user(user, a, mid, cache_dir), fetch_user(user, mid + 1, b, cache_dir)
        d = None if x is None or y is None else x + y
    if d is not None:
        _save(path, d)
    return d
