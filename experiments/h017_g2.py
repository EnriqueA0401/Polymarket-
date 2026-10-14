"""H017 G2 (entrenamiento): carry en NO de eventos improbables a 90 días.
python experiments/h017_g2.py → reports/h017_g2.md"""
import os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd, requests
from pmq import h001, h005, trades
from pmq.universe import DATA

H = pd.Timedelta("90D")
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                    columns=["id", "condition_id", "token_yes", "event_id", "y", "start", "end", "closed_time",
                             "enable_ob", "fee_schedule", "category", "question"])
t = u[(u.closed_time < h001.HOLDOUT_START) & u.enable_ob & (u.start <= u.end - pd.Timedelta("120D"))
      & (u.closed_time > u.end - H)].copy()
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
s = t[t.p.notna() & (t.p >= 0.02) & (t.p <= 0.10)].copy()
s["t1"] = [int(x.timestamp()) for x in s.t]
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda r: trades.fetch(r[0], r[1] - 3 * 86400, r[1], os.path.join(DATA, "trades_h017")),
                      zip(s.condition_id, s.t1)))
s["px"] = [h005.exec_price(r, 1, a - 3 * 86400, a) for r, a in zip(res, s.t1)]
b = s[s.px.notna() & (s.px < 0.999)].copy()
b["rate"] = [h001.fee_rate(x) for x in b.fee_schedule]
b["pnl"] = (1 - b.y) - b.px - b.rate * b.px * (1 - b.px)
b["days"] = ((b.closed_time - b.t).dt.total_seconds() / 86400).clip(lower=1)
b["ann"] = (b.pnl / b.px) * 365 / b.days                      # anualización simple
lo, hi = h001.cluster_bootstrap(b, col="ann") if len(b) > 5 else (np.nan, np.nan)
plo, phi_ = h001.cluster_bootstrap(b, col="pnl") if len(b) > 5 else (np.nan, np.nan)
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = ["# H017 G2 — carry en NO a 90 días (entrenamiento)", "", f"- commit {commit}",
     f"- elegibles {len(t):,}; con precio diario en t {t.p.notna().sum():,}; señal 0.02–0.10: {len(s):,}; "
     f"con compra real de NO en (t−3d, t]: {len(b):,} ({b.event_id.nunique():,} eventos)",
     f"- PnL medio {b.pnl.mean()*100:.3f} c/acción (IC95% {plo*100:.3f} … {phi_*100:.3f}); precio medio NO {b.px.mean():.4f}; "
     f"YES ocurrió en {int((b.y == 1).sum())} ({(b.y == 1).mean():.1%}), anulados {int((b.y == 0.5).sum())}",
     f"- rendimiento anualizado medio {b.ann.mean():.2%} (IC95% cluster {lo:.2%} … {hi:.2%}); días medios {b.days.mean():.0f}",
     f"- criterio: media > 6% y IC inferior > 4% → {'CUMPLE' if (b.ann.mean() > .06 and lo > .04) else 'NO cumple'}",
     "", "## Por categoría", "", b.groupby(b.category.fillna("NA")).agg(n=("pnl", "size"), pnl=("pnl", "mean"), ann=("ann", "mean")).round(4).to_markdown()]
open(os.path.join(ROOT, "reports", "h017_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L[:7]))
