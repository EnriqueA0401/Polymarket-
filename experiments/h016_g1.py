"""H016 G1: universo de barreras BTC/ETH (entrenamiento), reglas de resolución y concordancia del proxy
Binance 1m (High/Low tocó la barrera entre inicio y endDate) con la resolución de Polymarket.
python experiments/h016_g1.py → data/h016_g1.parquet, reports/h016_g1.md"""
import gzip, json, os, re, subprocess, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h016
from pmq.universe import DATA

THR = 0.97
COLS = ["id", "condition_id", "question", "y", "clean", "start", "end", "closed_time", "event_id", "series",
        "fee_schedule", "volume"]
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=COLS)
q = u.question.fillna("")
pre = q.str.contains(r"(?i)(?<![a-z])(?:bitcoin|btc|ethereum|eth)(?![a-z])") & q.str.contains(r"(?i)\b(?:reach|hit|dip|fall|drop)")
c = u[pre].copy()
del u
n_pre = len(c)
c["train"] = (c.end < h001.HOLDOUT_START) & (c.closed_time < h001.HOLDOUT_START)
n_hold = int((~c.train).sum())
c = c[c.train].copy()
P = c.question.map(h016.parse_question)
excl_parse = c[P.isna()]
c = c[P.notna()].copy()
c["asset"], c["X"], c["dir_q"] = zip(*P[P.notna()])

# descripciones (Gamma crudo por día de endDate)
want = set(c.id)
desc = {}
for d in sorted(set(c.end.dt.strftime("%Y-%m-%d"))):
    f = os.path.join(DATA, "gamma", f"win_{d}.jsonl.gz")
    if not os.path.exists(f):
        continue
    for l in gzip.open(f, "rt"):
        if '"id"' not in l:
            continue
        m = json.loads(l)
        if int(m["id"]) in want:
            desc[int(m["id"])] = (m.get("description") or "", m.get("resolutionSource") or "")
c["desc"] = c.id.map(lambda i: desc.get(i, ("", ""))[0])
c["res_src"] = c.id.map(lambda i: desc.get(i, ("", ""))[1])
c["source"] = (c.desc + " " + c.res_src).map(h016.source)
c["dir_d"] = c.desc.map(h016.desc_direction)
c["direction"] = c.dir_d.fillna(c.dir_q)
c["conflict"] = c.dir_d.notna() & (c.dir_d != c.dir_q)
c["grp"] = c.series.fillna("none:" + c.source).astype(str) + "|" + c.direction
c["month"] = c.end.dt.strftime("%Y-%m")
c["dur_d"] = (c.end - c.start).dt.total_seconds() / 86400

# proxy Binance
out = []
for a, g in c.groupby("asset"):
    k = h016.load_hl(h016.SYMBOL[a], g.start.min().floor("D") - pd.Timedelta("8D"), g.end.max().ceil("D"))
    kmin = k.index.min() if len(k) else pd.NaT
    prox, ext = [], []
    for r in g.itertuples():
        if pd.isna(r.start) or len(k) == 0 or r.start < kmin:
            prox.append(np.nan); ext.append(np.nan); continue
        w = k.loc[r.start: r.end - pd.Timedelta(microseconds=1)]
        if len(w) < 0.9 * max(1, (r.end - r.start).total_seconds() / 60):
            prox.append(np.nan); ext.append(np.nan); continue
        if r.direction == "up":
            e = float(w.high.max()); prox.append(float(e >= r.X))
        else:
            e = float(w.low.min()); prox.append(float(e <= r.X))
        ext.append(e / r.X - 1)
    out.append(g.assign(proxy=prox, ext_rel=ext))
c = pd.concat(out)
cc = c[c.clean & c.proxy.notna()].copy()
cc["ok"] = cc.proxy == cc.y
agr = cc.groupby("grp").agg(n=("ok", "size"), agree=("ok", "mean"), yes_rate=("y", "mean"))
agr["pasa"] = agr.agree >= THR
c["group_ok"] = c.grp.map(agr.pasa).fillna(False).astype(bool)
c.drop(columns=["desc"]).to_parquet(os.path.join(DATA, "h016_g1.parquet"))

# --------------------------------------------------------------------------- informe
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
md = lambda df: df.to_markdown()
L = ["# H016 G1 — barreras BTC/ETH: universo, reglas y concordancia proxy Binance", "",
     f"- commit {commit}; datos: universe_binary.parquet + data/gamma (descripciones) + Binance spot 1m mensual (data.binance.vision)",
     f"- candidatos por texto (activo + verbo): {n_pre:,}; fuera por holdout (end o closedTime ≥ {h001.HOLDOUT_START.date()}): {n_hold:,}",
     f"- entrenamiento descartados por el parser (0 o ≥2 importes, ambos activos — p.ej. 'hit $X or $Y first'): {len(excl_parse):,}",
     f"- entrenamiento parseados: {len(c):,} mercados, {c.event_id.nunique():,} eventos; limpios {int(c.clean.sum()):,}, anulados {int((~c.clean).sum()):,}",
     f"- con descripción encontrada: {int((c.res_src + c.id.map(lambda i: desc.get(i, ('', ''))[0])).str.len().gt(0).sum()):,}", "",
     "Ejemplos descartados por el parser: " + "; ".join(excl_parse.question.head(8).tolist()), "",
     "## Recuento por activo / dirección (dirección = regla de la descripción High/Low; si falta, texto)", "",
     md(c.groupby(["asset", "direction"]).size().unstack(fill_value=0)), "",
     "## Por serie", "", md(c.groupby(c.series.fillna("none")).agg(n=("id", "size"), dur_med_d=("dur_d", "median"),
                                                                  end_hora_utc=("end", lambda s: s.dt.hour.mode().iloc[0]))), "",
     "## Por mes de endDate", "", md(c.groupby(["month", "asset"]).size().unstack(fill_value=0)), "",
     "## Reglas de resolución (de las descripciones)", "",
     md(c.groupby([c.series.fillna("none"), "source"]).size().rename("n").to_frame()), "",
     f"- conflictos dirección texto vs descripción: {int(c.conflict.sum()):,} (p.ej. 'reach $2,000' con regla 'Low ≤ $2,000'; "
     "se usa SIEMPRE la regla de la descripción). Ejemplos: " + "; ".join(c[c.conflict].question.head(5).tolist()),
     "- Binance (series *-hit-price-*, btc/eth-monthly-prices): 'cualquier vela 1m de Binance BTC/USDT (ETH/USDT) con High ≥ X "
     "(o Low ≤ X)' entre inicio de ventana y 23:59 ET del último día; resolución inmediata a Yes al tocar.",
     "- CoinGecko (2021–2022, btc/eth-weeklies y sin serie): precio USD de CoinGecko (algunas velas 30 min low); fuente distinta del proxy.",
     "- endDate ≠ fin de ventana en btc/eth-monthly-prices (endDate 12:00 UTC del último día; la ventana acaba 23:59 ET ≈ 04:00 UTC del día siguiente). "
     "Protocolo: vencimiento = endDate (τ más corto que el real → se mantiene; el proxy de G1 mide el efecto).",
     "- Las series diarias (duración ≈ 1 día) no pueden estar abiertas en t = endDate − 3d: entran en G1 pero no generan observaciones en G2.", "",
     f"## Concordancia proxy (Binance tocó X en [start, endDate)) vs resolución, mercados limpios — umbral {THR:.0%}", "",
     md(agr.round(4)), "",
     f"- grupos que pasan: {', '.join(agr.index[agr.pasa]) or 'ninguno'}",
     f"- grupos excluidos: {', '.join(agr.index[~agr.pasa]) or 'ninguno'}",
     f"- sin proxy (sin klines/start anterior a datos): {int(c.proxy.isna().sum()):,}", "",
     "## Desacuerdos (proxy vs y) — distancia relativa del extremo Binance a la barrera", ""]
dis = cc[~cc.ok]
if len(dis):
    L += [md(dis.assign(ext_pct=(dis.ext_rel * 100).round(3))[["question", "grp", "y", "proxy", "ext_pct", "end", "closed_time"]].head(40)), ""]
open(os.path.join(ROOT, "reports", "h016_g1.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L[:12]))
print(agr)
