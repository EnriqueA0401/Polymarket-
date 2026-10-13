"""H006 G2 (solo entrenamiento): maker en extremos con fills pesimistas.
python experiments/h006_g2.py → reports/h006_g2.md (caché de trades en data/trades_h006)
python experiments/h006_g2.py rep → réplica pre-registrada (muestra h006r, solo 24h) → reports/h006_rep.md"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
from pmq import h001, h006, trades
from pmq.universe import DATA
from h001_g2 import load_histories, COLS

CACHE = os.path.join(DATA, "trades_h006")
REP = len(sys.argv) > 1 and sys.argv[1] == "rep"
hist = load_histories("h006r" if REP else "h001")
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=COLS + ["condition_id"])
u = u[u.id.isin(hist.keys()) & (u.closed_time < h001.HOLDOUT_START)]
cid = u.set_index("id").condition_id
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = [("# H006 réplica pre-registrada (eventos hash 150–449)" if REP else "# H006 G2 — maker en extremos (solo entrenamiento)"), "", f"- commit {commit}", ""]
for name, h in ([("24h", pd.Timedelta("24h"))] if REP else [("24h", pd.Timedelta("24h")), ("7d", pd.Timedelta("7D"))]):
    s = h006.signals(h001.observations(u, hist, h))
    t0 = [int(t.timestamp()) for t in s.t]
    jobs = [(cid[i], a, a + 86400) for i, a in zip(s.id, t0)]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda j: trades.fetch(j[0], j[1], j[2], CACHE), jobs))
    s = s.assign(fail=[r is None for r in res],
                 fill=[h006.filled(r, sd, p, a, a + 86400) for r, sd, p, a in zip(res, s.side, s.p, t0)])
    f = s[s.fill].copy()
    f["pnl"] = [h006.pnl(sd, lv, y) for sd, lv, y in zip(f.side, f.level, f.y)]
    f["ret"] = f.pnl / f.level
    lo, hi = h001.cluster_bootstrap(f, col="pnl") if len(f) else (np.nan, np.nan)
    L += [f"## Horizonte {name}", "",
          f"- señales {len(s):,} (long {int((s.side=='long').sum()):,}, fav {int((s.side=='fav').sum()):,}); "
          f"fallos descarga {int(s.fail.sum())}",
          f"- fill rate {s.fill.mean():.1%} ({len(f):,} fills, {f.event_id.nunique():,} eventos)",
          f"- PnL medio por acción {f.pnl.mean()*100:.3f} c (IC95% cluster {lo*100:.3f} … {hi*100:.3f}); "
          f"retorno medio {f.ret.mean():.3%}; días medios {((f.close - f.t).dt.total_seconds()/86400).mean():.2f}",
          "- por lado: " + "; ".join(f"{k}: fills {len(g):,}, PnL {g.pnl.mean()*100:.3f} c, fill rate "
                                    f"{s[s.side==k].fill.mean():.1%}" for k, g in f.groupby("side")),
          f"- PnL si se llenara TODO (sin selección por fill): {np.mean([h006.pnl(a,b,c) for a,b,c in zip(s.side,s.level,s.y)])*100:.3f} c "
          "(mide selección adversa)", ""]
open(os.path.join(ROOT, "reports", "h006_rep.md" if REP else "h006_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
