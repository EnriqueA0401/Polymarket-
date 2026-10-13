"""Coste real de ejecución hoy en la zona de señal (H001 extremos / H003 zona media).

Uso: python experiments/h001_live_costs.py [h003]

Toma mercados binarios ABIERTOS que cierran en 1–8 días, con mid ≤ 0.10 o ≥ 0.90, descarga
el libro CLOB del token a comprar (NO si mid ≤ 0.10, YES si mid ≥ 0.90) y calcula el precio
medio de compra de N USD barriendo el ask, frente al mid y al lastTradePrice.
Salida: reports/h001_live_costs.md + data/live_books_<fecha>.json
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd, requests

ROOT = os.path.join(os.path.dirname(__file__), "..")
MODE = sys.argv[1] if len(sys.argv) > 1 else "h001"
LO_D, HI_D = ("5D", "9D") if MODE == "h003" else ("1D", "8D")
G = "https://gamma-api.polymarket.com/markets/keyset"
now = pd.Timestamp.now(tz="UTC")
ms, c = [], None
while len(ms) < 20000:
    p = {"closed": "false", "limit": 100, "end_date_min": (now + pd.Timedelta(LO_D)).isoformat(),
         "end_date_max": (now + pd.Timedelta(HI_D)).isoformat()}
    if c: p["after_cursor"] = c
    d = requests.get(G, params=p, timeout=60).json()
    ms += d.get("markets") or []; c = d.get("next_cursor")
    if not c or not d.get("markets"): break
rows = []
for m in ms:
    try:
        toks = json.loads(m["clobTokenIds"]); bb, ba = float(m["bestBid"]), float(m["bestAsk"])
    except (KeyError, TypeError, ValueError):
        continue
    if len(toks) != 2 or not m.get("acceptingOrders"): continue
    mid = (bb + ba) / 2
    if MODE == "h003":
        if json.loads(m.get("outcomes") or "[]") == ["Yes", "No"] and .2 <= mid <= .8:
            rows.append((m["id"], toks[1], 1 - mid, m.get("lastTradePrice"), m.get("feeSchedule")))
        continue
    if mid <= .10: rows.append((m["id"], toks[1], 1 - mid, m.get("lastTradePrice"), m.get("feeSchedule")))
    elif mid >= .90: rows.append((m["id"], toks[0], mid, m.get("lastTradePrice"), m.get("feeSchedule")))
rng = np.random.default_rng(0)
rows = [rows[i] for i in rng.permutation(len(rows))[:600]]

def book(r):
    for i in range(4):
        try:
            b = requests.get("https://clob.polymarket.com/book", params={"token_id": r[1]}, timeout=30)
            if b.status_code == 200: return r, b.json()
        except requests.RequestException: pass
        time.sleep(2 ** i)
    return r, None

def sweep(asks, usd):
    asks = sorted(((float(a["price"]), float(a["size"])) for a in asks))
    spent = sh = 0.0
    for px, sz in asks:
        take = min(sz, (usd - spent) / px)
        spent += take * px; sh += take
        if spent >= usd - 1e-9: return spent / sh
    return np.nan  # no hay profundidad suficiente

out = []
with ThreadPoolExecutor(6) as ex:
    for r, b in ex.map(book, rows):
        if not b or not b.get("asks") or not b.get("bids"): continue
        best_ask = min(float(a["price"]) for a in b["asks"]); best_bid = max(float(x["price"]) for x in b["bids"])
        mid = (best_ask + best_bid) / 2
        out.append({"id": r[0], "mid": mid, "spread": best_ask - best_bid,
                    **{f"cost_{u}": sweep(b["asks"], u) - mid for u in (10, 50, 200)}})
df = pd.DataFrame(out)
os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
df.to_json(os.path.join(ROOT, "data", f"live_books_{MODE}_{now:%Y%m%d}.json"), orient="records")
q = df[["spread", "cost_10", "cost_50", "cost_200"]].describe(percentiles=[.1, .25, .5, .75, .9]).T
L = [f"# {MODE.upper()} — coste de ejecución real (libros CLOB, {now:%Y-%m-%d %H:%M} UTC)", "",
     f"- Mercados abiertos (cierre en {LO_D}–{HI_D}) en zona de señal muestreados: {len(df)} de {len(ms)} consultados", "",
     "Coste = precio medio de compra barriendo asks − mid (en $/acción); NaN = sin profundidad.", "",
     q.round(4).to_markdown(), "",
     f"- Fracción sin profundidad para 200 USD: {df.cost_200.isna().mean():.2%}"]
open(os.path.join(ROOT, "reports", f"{MODE}_live_costs.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
