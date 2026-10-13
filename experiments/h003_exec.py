"""H003: ¿eran ejecutables los precios? Recalcula el retorno con compras reales de NO.

Regla (fijada antes de ver el resultado): para cada operación de entrenamiento en t,
descargar trades taker de (t−24h, t] (Data API). Precio de entrada = MÁXIMO precio pagado
por compradores taker de NO en esa ventana (pesimista) + comisión. Sin compras de NO en la
ventana → operación no ejecutable (excluida y contada). Salida: reports/h003_exec.md
"""
import gzip, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd, requests
from pmq import h001, h003
from pmq.universe import DATA
from h001_g2 import load_histories, COLS

CACHE = os.path.join(DATA, "trades_h003"); os.makedirs(CACHE, exist_ok=True)


def trades(cid, a, b):
    path = os.path.join(CACHE, f"{cid}_{a}_{b}.json.gz")
    if os.path.exists(path):
        return json.load(gzip.open(path, "rt"))
    for i in range(6):
        try:
            r = requests.get("https://data-api.polymarket.com/trades",
                             params={"market": cid, "takerOnly": "true", "start": a, "end": b, "limit": 10000}, timeout=60)
            if r.status_code == 200:
                d = [{k: x[k] for k in ("side", "outcome", "price", "size", "timestamp")} for x in r.json()]
                json.dump(d, gzip.open(path, "wt"))
                return d
        except requests.RequestException:
            pass
        time.sleep(2 ** i)
    return None


hist = load_histories()
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=COLS + ["outcome0", "condition_id"])
u = u[u.id.isin(hist.keys()) & (u.closed_time < h001.HOLDOUT_START)]
cid = u.set_index("id").condition_id
L = ["# H003 — ejecutabilidad con trades reales (entrenamiento, Yes/No)", ""]
for name, h in [("24h", pd.Timedelta("24h")), ("7d", pd.Timedelta("7D"))]:
    tr = h003.trades(h003.observations(u, hist, h).query("yesno"))
    jobs = [(cid[i], int(t.timestamp()) - 86400, int(t.timestamp())) for i, t in zip(tr.id, tr.t)]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda j: trades(*j), jobs))
    px = [max((x["price"] for x in (r or []) if x["side"] == "BUY" and x["outcome"] == "No"), default=np.nan) for r in res]
    tr = tr.assign(no_px=px, fail=[r is None for r in res])
    ex_ = tr[tr.no_px.notna()].copy()
    q = ex_.no_px.clip(upper=0.999)
    fee = ex_.fee_rate * q * (1 - q)
    ex_["ret_exec"] = (ex_.payoff - q - fee) / (q + fee)
    lo, hi = h001.cluster_bootstrap(ex_, col="ret_exec") if len(ex_) else (np.nan, np.nan)
    L += [f"## Horizonte {name}", "",
          f"- operaciones señal: {len(tr):,}; fallos de descarga: {int(tr.fail.sum())}; con compras taker de NO "
          f"en (t−24h, t]: {len(ex_):,} ({len(ex_)/max(len(tr),1):.1%})",
          f"- retorno con precio histórico+0.02 (mismas ops): {ex_.ret.mean():.3%}",
          f"- retorno con peor precio real de compra de NO: {ex_.ret_exec.mean():.3%} (IC95% cluster {lo:.3%} … {hi:.3%})",
          f"- diferencia media precio real − (1−p): {(ex_.no_px - (1 - ex_.p)).mean():+.4f}", ""]
open(os.path.join(ROOT, "reports", "h003_exec.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
