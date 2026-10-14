"""H023 G2 (solo entrenamiento): lead-lag Kalshi → Polymarket pre-partido, regla única del protocolo G0
y placebo con los timestamps de Kalshi desplazados −10 min.
Requiere haber ejecutado experiments/h023_g1.py (cachés). python experiments/h023_g2.py → reports/h023_g2.md"""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h023 as H, h001, h004, trades
from pmq.universe import DATA

PM_CACHE = os.path.join(DATA, "trades_h023")
g = pd.read_parquet(os.path.join(H.CACHE, "matches.parquet")).set_index("id")
cands = pd.read_parquet(os.path.join(H.CACHE, "cands.parquet"))
wj = pd.read_parquet(os.path.join(H.CACHE, "pm_windows.parquet"))


def pm_fetch(cid, a, b):   # idéntico a G1 (solo lee caché)
    d = trades.fetch(cid, a, b, PM_CACHE)
    if d is not None and len(d) >= 10000 and b - a > 120:
        mid = (a + b) // 2
        x, y = pm_fetch(cid, a, mid), pm_fetch(cid, mid + 1, b)
        d = None if x is None or y is None else x + y
    return d


rows, diag = [], []
for gid, grp in wj.groupby("id"):
    r = g.loc[gid]
    tr = []
    for a, b in zip(grp.a, grp.b):
        d = pm_fetch(r.condition_id, int(a), int(b))
        tr += d or []
    seen, ded = set(), []
    for x in tr:                       # trozos con bordes inclusivos → posibles duplicados
        k = (x["timestamp"], x["price"], x["size"], x["outcomeIndex"], x["side"])
        if k not in seen:
            seen.add(k); ded.append(x)
    pt, pp = H.pm_series(ded)
    for shift in (0, -600):
        c = cands[(cands.id == gid) & (cands["shift"] == shift)]
        cl = sorted(zip(c.t.values, c.dk.values))
        for s in H.signals(cl, pt, pp):
            t = s["t"]
            px = H.exec_price(ded, s["idx"], t + H.ENTRY_LAG, t + H.ENTRY_END)
            buys = [float(x["price"]) for x in ded if x["outcomeIndex"] == s["idx"] and x["side"] == "BUY"
                    and t + H.ENTRY_LAG < x["timestamp"] <= t + H.ENTRY_END]
            p5 = H.last_price(pt, pp, t + H.ENTRY_END)
            rows.append({"id": gid, "shift": shift, "league": r.league, "season": r.season, **s,
                         "px": px, "med": float(np.median(buys)) if buys else np.nan, "y": r.y, "rate": r.rate,
                         "pm_resp": (p5 - s["pm1"]) * np.sign(s["dk"]), "mins_to_start": (r.gs - t) / 60})
sig = pd.DataFrame(rows)
sig.to_parquet(os.path.join(H.CACHE, "signals.parquet"))


def evaluate(s):
    b = s[s.px.notna()].copy()
    if b.empty:
        return b
    b["pnl"] = [H.pnl(i, p, r, y) for i, p, r, y in zip(b.idx, b.px, b.rate, b.y)]
    b["px2"] = np.minimum(b.px + np.maximum(0.01, b.px - b.med), 0.999)
    b["pnl2"] = [H.pnl(i, p, r, y, cost_mult=2) for i, p, r, y in zip(b.idx, b.px2, b.rate, b.y)]
    b["ret"] = b.pnl / b.px
    b["gross"] = np.where(b.idx == 0, b.y, 1 - b.y) - b.px
    return b


def line(name, b, col="pnl"):
    if len(b) == 0:
        return f"| {name} | 0 | 0 | – | – | – |"
    lo, hi = h001.cluster_bootstrap(b, col=col, cluster="id") if b.id.nunique() > 1 else (np.nan, np.nan)
    return (f"| {name} | {len(b):,} | {b.id.nunique():,} | {b[col].mean()*100:+.2f} | "
            f"[{lo*100:+.2f}, {hi*100:+.2f}] | {b.px.mean():.3f} |")


HDR = ["| conjunto | operaciones | partidos | PnL medio c/acción | IC95% cluster (partido) | precio medio |",
       "|---|---:|---:|---:|---:|---:|"]
res = {}
for shift in (0, -600):
    s = sig[sig["shift"] == shift] if len(sig) else sig
    res[shift] = (s, evaluate(s) if len(s) else s)
s0, b0 = res[0]
sp, bp = res[-600]
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()

L = ["# H023 G2 — lead-lag Kalshi → Polymarket pre-partido (solo entrenamiento)", "",
     f"- commit {commit}; partidos emparejados con resolución verificada: {len(g):,}; con candidatos Kalshi: "
     f"{cands[cands['shift'] == 0].id.nunique():,}",
     "- Regla (G0, variante única): |ΔK| ≥ 0.05 en 2 min (último trade del mercado Kalshi del equipo outcome0), "
     "|ΔPM| < 0.02 en la misma ventana, t + 5 min ≤ gameStartTime; entrada = peor compra taker real en PM del "
     "lado del movimiento en (t+30 s, t+5 min]; hasta resolución; comisión feeSchedule o 0.07.",
     ""]
if len(s0) == 0:
    L += ["**Sin señales.**"]
else:
    nt = b0[~b0.id.isin(b0.groupby("id").pnl.sum().sort_values(ascending=False).index[:5])]
    L += [f"- señales: {len(s0):,} en {s0.id.nunique():,} partidos; con fill real en PM: {len(b0):,} "
          f"({len(b0)/len(s0):.1%}) en {b0.id.nunique():,} partidos",
          f"- |ΔK| medio {s0.dk.abs().mean():.3f}; minutos hasta el inicio: mediana {s0.mins_to_start.median():.0f}",
          f"- respuesta de PM en la dirección de Kalshi entre t y t+5 min (último trade): media "
          f"{s0.pm_resp.mean()*100:+.2f} c (n={s0.pm_resp.notna().sum():,})",
          "", "## Resultado principal", "", *HDR,
          line("TODAS (neto)", b0), line("bruto (sin comisión)", b0, "gross"), line("costes ×2", b0, "pnl2"),
          line("sin top-5 partidos", nt), line("primera señal por partido (diagnóstico)", b0.drop_duplicates("id")),
          *[line(f"liga {lg}", b0[b0.league == lg]) for lg in sorted(b0.league.unique())],
          *[line(f"{'Kalshi sube' if i == 0 else 'Kalshi baja'} (idx {i})", b0[b0.idx == i]) for i in (0, 1)],
          "", f"- retorno medio por dólar: {b0.ret.mean():+.2%}; PnL total {b0.pnl.sum():+.2f} por acción-señal",
          "", "## Placebo: timestamps de Kalshi desplazados −10 min", "",
          f"- señales: {len(sp):,} en {sp.id.nunique() if len(sp) else 0:,} partidos; con fill {len(bp):,}",
          f"- respuesta PM t→t+5 min: {sp.pm_resp.mean()*100:+.2f} c" if len(sp) else "", "", *HDR,
          line("placebo (neto)", bp), line("placebo costes ×2", bp, "pnl2") if len(bp) else "",
          ]
    lo, hi = h001.cluster_bootstrap(b0, col="pnl", cluster="id")
    met = (b0.pnl.mean() > 0) and (lo > 0) and (b0.id.nunique() >= 150)
    L += ["", "## Predicción G0", "",
          f"- PnL > 0 con IC95% cluster > 0 y ≥ 150 partidos: **{'CUMPLIDA' if met else 'NO CUMPLIDA'}** "
          f"(PnL {b0.pnl.mean()*100:+.2f} c, IC [{lo*100:+.2f}, {hi*100:+.2f}], partidos {b0.id.nunique():,})"]
L += ["", "## Notas", "",
      "- Variantes usadas: 1 (regla única). Placebo y desgloses son diagnósticos, no variantes seleccionables.",
      "- Costes ×2: comisión ×2 y slippage adicional = max(0.01, peor − mediana de compras del lado en la ventana).",
      "- El precio de entrada es el PEOR trade taker real de compra en la ventana (no midpoint ni prices-history).",
      "- Sin fill (ningún comprador taker del lado en la ventana) → no se opera (no se asume fill de límite).",
      "- Limitaciones: la latencia real API Kalshi → orden PM podría superar 30 s en momentos de noticias; "
      "los trades de Kalshi muestran el último precio, no el libro."]
open(os.path.join(ROOT, "reports", "h023_g2.md"), "w").write("\n".join(x for x in L if x is not None) + "\n")
print("\n".join(L))
