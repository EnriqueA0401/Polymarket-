"""Red team H024 (carry en NO a 90 días). Solo ANALIZA los ficheros por operación ya existentes
(data/h017_trades.parquet = entrenamiento, data/h024_trades.parquet = holdout) y la caché de trades
data/trades_h017 (volumen de compras taker de NO en la ventana de entrada). No re-evalúa el holdout.
python experiments/h024_redteam.py [train.parquet] [hold.parquet] → imprime las cifras de reports/h024_redteam.md
"""
import gzip, json, os, sys
import numpy as np, pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
TR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DATA, "h017_trades.parquet")
HO = sys.argv[2] if len(sys.argv) > 2 else os.path.join(DATA, "h024_trades.parquet")
HOLD0 = pd.Timestamp("2026-04-12", tz="UTC")
CUT = pd.Timestamp("2026-10-12", tz="UTC")      # fecha de ingesta de Gamma (data/gamma)
rng = np.random.default_rng(0)

u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=["id", "event_id", "closed_time", "volume", "neg_risk"])
ev_min, ev_max = u.groupby("event_id").closed_time.min(), u.groupby("event_id").closed_time.max()


def liq(b):
    usd, med = [], []
    for c, a in zip(b.condition_id, b.t1):
        r = json.load(gzip.open(os.path.join(DATA, "trades_h017", f"{c}_{a - 3 * 86400}_{a}.json.gz"), "rt"))
        x = [t for t in r if t["outcomeIndex"] == 1 and t["side"] == "BUY"]
        usd.append(sum(float(t["size"]) * float(t["price"]) for t in x))
        med.append(np.median([float(t["price"]) for t in x]))
    return usd, med


def bm(df, col, cl="event_id", n=2000):
    g = df.groupby(cl)[col].agg(["sum", "count"]); s, c = g["sum"].values, g["count"].values
    idx = rng.integers(0, len(g), (n, len(g)))
    return np.round(np.percentile(s[idx].sum(1) / c[idx].sum(1), [2.5, 97.5]) * 100, 2)


def br(df, col="pnl", cl="event_id", n=2000):
    """IC de la rentabilidad sobre capital×tiempo: Σpnl / Σ(px·días) × 365."""
    d = df.assign(cd=df.px * df.days)
    g = d.groupby(cl).agg(a=(col, "sum"), c=("cd", "sum")); a, c = g.a.values, g.c.values
    idx = rng.integers(0, len(g), (n, len(g)))
    return np.round(np.percentile(a[idx].sum(1) / c[idx].sum(1) * 365 * 100, [2.5, 97.5]), 2)


def summ(nm, x, col="pnl"):
    port = x[col].sum() / (x.px * x.days).sum() * 365
    print(f"{nm:44s} n={len(x):4d} ev={x.event_id.nunique():4d} pnl={x[col].mean()*100:6.3f}c IC{bm(x, col)} "
          f"ann_medio={x.ann.mean():7.2%} cartera={port:6.2%} IC{br(x, col)}")


def theme(q):
    import re
    q = str(q).lower()
    q = re.sub(r"\b(by|before|in|on|end of|after)\b.*$", "", q)
    q = re.sub(r"january|february|march|april|may|june|july|august|september|october|november|december", "", q)
    q = re.sub(r"[\d$%,.\-]+", "", q)
    return " ".join(q.split()[:4])


for nm, p in (("ENTRENAMIENTO", TR), ("HOLDOUT", HO)):
    x = pd.read_parquet(p).drop(columns=["volume", "neg_risk"], errors="ignore").merge(u[["id", "volume", "neg_risk"]], on="id")
    x["no_buy_usd"], x["med_px"] = liq(x)
    x["ev_min"], x["ev_max"] = x.event_id.map(ev_min), x.event_id.map(ev_max)
    x["theme"], x["endm"] = x.question.map(theme), x.end.dt.strftime("%Y-%m")
    print(f"\n== {nm} ==")
    summ("todo", x)
    print(f"  días<7: n={(x.days < 7).sum()}; ann_medio sin ellos {x[x.days >= 7].ann.mean():.2%}; winsor 1% {x.ann.clip(upper=x.ann.quantile(.99)).mean():.2%}")
    print(f"  IC pnl cluster=tema {bm(x, 'pnl', 'theme')}  cluster=mes de end {bm(x, 'pnl', 'endm')}; cartera IC tema {br(x, cl='theme')}")
    for k, s in ((0.005, "+0.5c"), (0.01, "+1c")):
        x["pk"] = 1 - x.y - (x.px + k) - 2 * x.rate * x.px * (1 - x.px)
        summ(f"costes x2 ({s} slippage, comisión x2)", x, "pk")
    summ("1 mercado aleatorio por evento", x.sample(frac=1, random_state=0).drop_duplicates("event_id"))
    summ("negRisk", x[x.neg_risk]); summ("no negRisk", x[~x.neg_risk])
    summ("compras NO en ventana >= 500 USD", x[x.no_buy_usd >= 500])
    print("  compras taker de NO en (t-3d,t], USD, cuantiles", x.no_buy_usd.quantile([.25, .5, .75]).round(0).tolist(),
          f"; >=1000 USD: {(x.no_buy_usd >= 1000).mean():.0%}; px - mediana {(x.px - x.med_px).mean()*100:.2f}c")
    print(f"  YES extra para PnL=0: {x.pnl.sum():.1f} (observados {int(x.y.sum())}, implícitos {(1 - x.px).sum():.1f})")
    print("  PnL por tercil de volumen", x.groupby(pd.qcut(x.volume, 3, labels=False)).pnl.mean().round(4).tolist())
    x["exit"] = x.t + pd.to_timedelta(x.days, unit="D")
    e = pd.concat([pd.DataFrame({"ts": x.t, "d": 1}), pd.DataFrame({"ts": x.exit, "d": -1})]).sort_values("ts")
    mx, span = e.d.cumsum().max(), (x.exit.max() - x.t.min()).days / 365
    print(f"  cartera igual-ponderada: máx. simultáneas {mx}, uso medio {(x.days.sum()/365/span)/mx:.0%}, "
          f"rentab./año sobre capital pico {(x.pnl/x.px).sum()/mx/span:.2%}; 1000 USD → {1000/mx:.1f} USD/posición")
    if nm == "HOLDOUT":
        summ("sin end > fecha de datos (censura)", x[x.end <= CUT])
        summ("sin censura ni eventos partidos train/holdout", x[(x.end <= CUT) & (x.ev_min >= HOLD0)])
        summ("solo entradas t >= inicio holdout", x[x.t >= HOLD0])
    else:
        summ("sin eventos con hermanos cerrados en holdout", x[x.ev_max < HOLD0])
