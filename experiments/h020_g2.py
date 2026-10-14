"""H020 G2 (entrenamiento): deriva de la primera hora tras el primer trade taker.
python experiments/h020_g2.py → data/h020_g2.parquet (caché de señales) y reports/h020_g2.md"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h004, h020, trades
from pmq.fetch_prices import ev_hash
from pmq.universe import DATA

CACHE = os.path.join(DATA, "trades_h020")
OUT = os.path.join(DATA, "h020_g2.parquet")
C = h001.HOLDOUT_START

u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                    columns=["condition_id", "event_id", "y", "start", "end", "closed_time", "series", "volume", "fee_schedule"])
cnt = [("universo binario", len(u))]
m = u[(u.closed_time < C) & (u.end < C)]; cnt.append(("entrenamiento (end y closedTime < 2026-04-12)", len(m)))
m = m[m.volume >= 5000]; cnt.append(("volumen ≥ 5,000 USD", len(m)))
m = m[~m.series.fillna("").str.contains("up-or-down")]; cnt.append(("sin series cripto Up/Down", len(m)))
m = m[m.start.notna() & m.condition_id.notna()]; cnt.append(("con start y conditionId", len(m)))
m = m[[ev_hash(e) < 50 for e in m.event_id]].copy(); cnt.append(("muestra sha256(event_id) mod 1000 < 50", len(m)))
del u
m["event_id"] = m.event_id.astype(object).where(m.event_id.notna(), m.condition_id)


def work(r):
    cid, s, c = r
    f = lambda k, a, b: trades.fetch(k, a, b, CACHE)
    a0, n, st = h020.first_trade(f, cid, int(s.timestamp()), int(c.timestamp()))
    row = {"condition_id": cid, "status": st, "a0": a0, "calls": n}
    if a0 is None:
        return row
    tr, _ = h020.fetch_all(f, cid, a0, a0 + h020.ENTRY[1])
    if tr is None:
        row["status"] = "fallo ventana"
        return row
    d, p0, v, dr = h020.signal(tr, a0)
    (pxy, mdy), (pxn, mdn) = h020.entry(tr, 0, a0), h020.entry(tr, 1, a0)
    row.update(n_tr=len(tr), dir=d, p0=p0, v=v, drift=dr, px_yes=pxy, med_yes=mdy, px_no=pxn, med_no=mdn)
    return row


if os.path.exists(OUT):
    s = pd.read_parquet(OUT)
else:
    with ThreadPoolExecutor(6) as ex:
        rows = []
        for i, row in enumerate(ex.map(work, zip(m.condition_id, m.start, m.closed_time))):
            rows.append(row)
            if i % 500 == 0:
                print(i, flush=True)
    s = pd.DataFrame(rows)
    s.to_parquet(OUT)

m = m.merge(s, on="condition_id", how="left")
ok = m[m.status == "ok"]; cnt.append(("con primer trade taker encontrado (a0)", len(ok)))
fail = m.status.value_counts().to_dict()
ok = ok[ok.p0.notna()]; cnt.append(("con trade YES en [a0, a0+60m]", len(ok)))
ok = ok[ok.v.notna()]; cnt.append(("con trades YES en [a0+50m, a0+60m] (VWAP)", len(ok)))
sig = ok[ok["dir"] != 0].copy(); cnt.append(("|deriva| ≥ 0.05 y VWAP en [0.10, 0.90]", len(sig)))
sig["rate"] = [h001.fee_rate(x) for x in sig.fee_schedule]


def line(name, b, col="pnl"):
    lo, hi = h001.cluster_bootstrap(b, col=col)
    return (f"- {name}: n={len(b):,} ({b.event_id.nunique():,} eventos); PnL {b[col].mean()*100:+.3f} c/acción "
            f"(IC95% cluster {lo*100:+.3f} … {hi*100:+.3f}); p unilateral {h020.cluster_p(b, col):.4f}")


res, pv, L2 = {}, [], []
for var in ["A", "B"]:
    b = sig.copy()
    b["idx"] = [h020.side(d, var) for d in b["dir"]]
    b["px"] = np.where(b.idx == 0, b.px_yes, b.px_no).astype(float)
    b["med"] = np.where(b.idx == 0, b.med_yes, b.med_no).astype(float)
    n_sig = len(b)
    b = b[b.px.notna()].copy()
    b["pnl"] = [h004.pnl(i, p, r, y) for i, p, r, y in zip(b.idx, b.px, b.rate, b.y)]
    # costes ×2: comisión ×2 y slippage adicional = max(0.01, peor − mediana de compras en la ventana de entrada)
    b["px2"] = np.minimum(b.px + np.maximum(0.01, b.px - b.med), 0.999)
    b["pnl2"] = [h004.pnl(i, p, 2 * r, y) for i, p, r, y in zip(b.idx, b.px2, b.rate, b.y)]
    res[var] = b
    pv.append(h020.cluster_p(b))
    top = b.groupby("event_id").pnl.sum().sort_values(ascending=False).index[:5]
    nt = b[~b.event_id.isin(top)]
    up = b["dir"] > 0
    L2 += [f"### Variante {var} ({'momentum' if var == 'A' else 'reversión'})", "",
           f"- señales {n_sig:,}; con compra taker real del token en (a0+60m, a0+120m]: {len(b):,}",
           line("PnL neto", b), line("costes ×2", b, "pnl2"), line("sin top-5 eventos", nt),
           f"- deriva al alza {int(up.sum())} (PnL {b[up].pnl.mean()*100:+.3f} c) / a la baja {int((~up).sum())} "
           f"(PnL {b[~up].pnl.mean()*100:+.3f} c)",
           f"- precio medio de entrada {b.px.mean():.3f}; pago medio del token {np.where(b.idx == 0, b.y, 1 - b.y).mean():.3f}; "
           f"anulados {(b.y == 0.5).sum()}; mediana horas a resolución "
           f"{((b.closed_time - pd.to_datetime(b.a0 + 7200, unit='s', utc=True)).dt.total_seconds() / 3600).median():.0f}",
           ""]
rej = h020.holm(pv)
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = ["# H020 G2 — deriva de la primera hora en mercados nuevos (entrenamiento)", "", f"- commit {commit}; datos: "
     f"universe_binary.parquet + Data API trades (caché data/trades_h020/)", "",
     "## Filtros", "", *[f"- {k}: {v:,}" for k, v in cnt], f"- estado de la búsqueda de a0: {fail}", "",
     "## Resultados", "", *L2,
     f"## Holm (2 pruebas, α=0.05)", "", f"- p A = {pv[0]:.4f}, p B = {pv[1]:.4f} → rechazo H0: A {rej[0]}, B {rej[1]}",
     "- Predicción (una variante con PnL > 0, IC95% > 0 y p Holm < 0.05): " +
     ("CUMPLIDA" if any(r and res[v].pnl.mean() > 0 and h001.cluster_bootstrap(res[v], col="pnl")[0] > 0
                        for r, v in zip(rej, "AB")) else "NO cumplida"), "",
     "## Notas de implementación", "",
     "- a0 = mínimo timestamp de trades taker (takerOnly=true) del mercado, buscado en [0, start+3d] y, si vacío, "
     "en ventanas crecientes hasta closedTime+1d; descenso por ventanas cuando la API devuelve 10,000.",
     "- p0 = precio del primer trade del token YES (outcomeIndex 0) en [a0, a0+60m] (VWAP si hay varios en ese segundo); "
     "VWAP = trades taker del token YES (compras y ventas) en [a0+50m, a0+60m]. Sin trades YES → sin señal.",
     "- 'precio YES actual' = esa VWAP. Entrada = peor compra taker del token en (a0+60m, a0+120m]; sin compra → sin operación.",
     "- Comisión = rate·p·(1−p) con rate de feeSchedule (0.07 si falta, pesimista). Anulados pagan 0.5. Clusters = evento.",
     "- p unilateral: aproximación normal con error estándar robusto por clusters (evento)."]
open(os.path.join(ROOT, "reports", "h020_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
