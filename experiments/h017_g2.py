"""H017 G2 (entrenamiento): carry en NO de eventos improbables a 90 días.
python experiments/h017_g2.py → reports/h017_g2.md
python experiments/h017_g2.py holdout → H024 G3 (UNA sola vez) → reports/h024_g3.md"""
import os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd, requests
from pmq import h001, h005, trades
from pmq.universe import DATA

H = pd.Timedelta("90D")
HOLD = len(sys.argv) > 1 and sys.argv[1] == "holdout"
FAV = len(sys.argv) > 1 and sys.argv[1] == "fav"          # H025: lado favorito (YES 0.90–0.98)
EXTRACT = len(sys.argv) > 2 and sys.argv[2] == "extract"
if HOLD and os.path.exists(os.path.join(ROOT, "reports", "h024_g3.md")) and not EXTRACT:
    sys.exit("El holdout de H024 ya se usó: no se repite (CLAUDE.md G3). Solo 'holdout extract' "
             "re-ejecuta EXACTAMENTE el mismo cálculo para guardar el detalle y verifica que coincide.")
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                    columns=["id", "condition_id", "token_yes", "event_id", "y", "start", "end", "closed_time",
                             "enable_ob", "fee_schedule", "category", "question"])
per = (u.closed_time >= h001.HOLDOUT_START) if HOLD else (u.closed_time < h001.HOLDOUT_START)
t = u[per & u.enable_ob & (u.start <= u.end - pd.Timedelta("120D")) & (u.closed_time > u.end - H)].copy()
t["t"] = t.end - H


def daily(tok):
    for i in range(5):
        try:
            r = requests.get("https://clob.polymarket.com/prices-history",
                             params={"market": tok, "interval": "max", "fidelity": 1440}, timeout=60)
            if r.status_code == 200:
                return r.json().get("history", [])
        except requests.RequestException:
            pass
        time.sleep(2 ** i)
    return None


with ThreadPoolExecutor(6) as ex:
    hs = list(ex.map(daily, t.token_yes))
t["p"] = [h001.price_at(h or [], tt.timestamp(), 3 * 86400) if h else None for h, tt in zip(hs, t.t)]
s = (t[t.p.notna() & (t.p >= 0.90) & (t.p <= 0.98)] if FAV else t[t.p.notna() & (t.p >= 0.02) & (t.p <= 0.10)]).copy()
IDX = 0 if FAV else 1
s["t1"] = [int(x.timestamp()) for x in s.t]
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda r: trades.fetch(r[0], r[1] - 3 * 86400, r[1], os.path.join(DATA, "trades_h017")),
                      zip(s.condition_id, s.t1)))
s["px"] = [h005.exec_price(r, IDX, a - 3 * 86400, a) for r, a in zip(res, s.t1)]
b = s[s.px.notna() & (s.px < 0.999)].copy()
b["rate"] = [h001.fee_rate(x) for x in b.fee_schedule]
b["pnl"] = (b.y if FAV else 1 - b.y) - b.px - b.rate * b.px * (1 - b.px)
b["days"] = ((b.closed_time - b.t).dt.total_seconds() / 86400).clip(lower=1)
b["ann"] = (b.pnl / b.px) * 365 / b.days                      # anualización simple
lo, hi = h001.cluster_bootstrap(b, col="ann") if len(b) > 5 else (np.nan, np.nan)
if HOLD:
    import glob, gzip, json
    ids, hr = set(b.id), {}
    for f in sorted(glob.glob(os.path.join(DATA, "gamma", "win_2026-*.jsonl.gz"))):
        for l in gzip.open(f, "rt"):
            m = json.loads(l)
            if int(m["id"]) in ids:
                hr[int(m["id"])] = bool(m.get("holdingRewardsEnabled"))
    b["hold_rw"] = b.id.map(hr).fillna(False)
    b["ann_hr"] = b.ann + np.where(b.hold_rw, 0.04, 0.0)
    lo2, hi2 = h001.cluster_bootstrap(b, col="ann_hr") if len(b) > 5 else (np.nan, np.nan)
plo, phi_ = h001.cluster_bootstrap(b, col="pnl") if len(b) > 5 else (np.nan, np.nan)
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = [("# H025 G2 — favoritos YES 0.90–0.98 a 90 días (entrenamiento)" if FAV else None) or ("# H024 G3 — HOLDOUT (una sola ejecución): carry en NO a 90 días + holding rewards" if HOLD
      else "# H017 G2 — carry en NO a 90 días (entrenamiento)"), "", f"- commit {commit}",
     f"- elegibles {len(t):,}; con precio diario en t {t.p.notna().sum():,}; señal {'0.90–0.98' if FAV else '0.02–0.10'}: {len(s):,}; "
     f"con compra real de {'YES' if FAV else 'NO'} en (t−3d, t]: {len(b):,} ({b.event_id.nunique():,} eventos)",
     f"- PnL medio {b.pnl.mean()*100:.3f} c/acción (IC95% {plo*100:.3f} … {phi_*100:.3f}); precio medio {'YES' if FAV else 'NO'} {b.px.mean():.4f}; "
     f"YES ocurrió en {int((b.y == 1).sum())} ({(b.y == 1).mean():.1%}), anulados {int((b.y == 0.5).sum())}",
     f"- rendimiento anualizado medio {b.ann.mean():.2%} (IC95% cluster {lo:.2%} … {hi:.2%}); días medios {b.days.mean():.0f}",
     f"- criterio: media > 6% y IC inferior > 4% → {'CUMPLE' if (b.ann.mean() > .06 and lo > .04) else 'NO cumple'}",
     *([f"- con holding reward (+4%/año si holdingRewardsEnabled; {int(b.hold_rw.sum())} de {len(b)} mercados): "
        f"anualizado medio {b.ann_hr.mean():.2%} (IC95% {lo2:.2%} … {hi2:.2%})",
        f"- H024 (a) PnL>0 e IC>0: {'SÍ' if plo > 0 else 'NO'}; (b) anualizado con HR >6% e IC inf >4%: "
        f"{'SÍ' if (b.ann_hr.mean() > .06 and lo2 > .04) else 'NO'}"] if HOLD else []),
     "", "## Por categoría", "", b.groupby(b.category.fillna("NA")).agg(n=("pnl", "size"), pnl=("pnl", "mean"), ann=("ann", "mean")).round(4).to_markdown()]
tag = "h025" if FAV else "h024" if HOLD else "h017"
b.to_parquet(os.path.join(DATA, f"{tag}_trades.parquet"))
if EXTRACT:
    prev = open(os.path.join(ROOT, "reports", "h024_g3.md")).read().splitlines()
    assert prev[3:9] == L[3:9], "la re-ejecución NO coincide con el informe original"
    print("EXTRACT OK: coincide con reports/h024_g3.md")
else:
    open(os.path.join(ROOT, "reports", "h025_g2.md" if FAV else "h024_g3.md" if HOLD else "h017_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L[:7]))
