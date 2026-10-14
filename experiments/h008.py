"""H008 formación (F) y test (T). python experiments/h008.py → reports/h008_g2.md
Cachés: data/trades_h008_mkt (mercados F), data/trades_h008_user, data/trades_h008_copy."""
import glob, gzip, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h008, trades
from pmq.universe import DATA

F0, F1 = pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2026-01-01", tz="UTC")
T0, T1 = F1, h001.HOLDOUT_START
ids = set()
for p in ("h001", "h006r"):
    for f in glob.glob(os.path.join(DATA, "prices", f"{p}_*.jsonl.gz")):
        for l in gzip.open(f, "rt"):
            ids.add(json.loads(l)["id"])
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                    columns=["id", "condition_id", "event_id", "closed_time", "volume", "y", "fee_schedule"])
fm = u[u.id.isin(ids) & (u.closed_time >= F0) & (u.closed_time < F1) & (u.volume >= 10_000)]
print("formación mercados", len(fm), flush=True)
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda c: trades.fetch_market_full(c, os.path.join(DATA, "trades_h008_mkt")), fm.condition_id))
rows = []
for (cid, ev, y), r in zip(fm[["condition_id", "event_id", "y"]].itertuples(index=False), res):
    for x in r or []:
        rows.append((x["proxyWallet"], ev, h008.trade_pnl(x["side"], x["outcomeIndex"], float(x["price"]), float(x["size"]), y)))
tr = pd.DataFrame(rows, columns=["proxyWallet", "event_id", "pnl"])
rank = h008.rank_wallets(tr)
top = rank.head(h008.TOP_K)
print("trades F", len(tr), "wallets elegibles", len(rank), flush=True)

# --- Test T: copiar BUYs de las top wallets
uc = u.set_index("condition_id")
a, b = int(T0.timestamp()), int(T1.timestamp())
with ThreadPoolExecutor(4) as ex:
    ut = list(ex.map(lambda w: trades.fetch_user(w, a, b, os.path.join(DATA, "trades_h008_user")), top.index))
cands = []
for w, r in zip(top.index, ut):
    seen = set()
    for x in sorted(r or [], key=lambda z: z["timestamp"]):
        if x["side"] != "BUY" or x["conditionId"] not in uc.index:
            continue
        key = (x["conditionId"], x["outcomeIndex"])
        if key in seen:
            continue
        seen.add(key)
        m = uc.loc[x["conditionId"]]
        if isinstance(m, pd.DataFrame):
            m = m.iloc[0]
        if not (m.closed_time > pd.Timestamp(x["timestamp"], unit="s", tz="UTC")):
            continue
        cands.append({"wallet": w, "cid": x["conditionId"], "idx": x["outcomeIndex"], "ts": x["timestamp"],
                      "event_id": m.event_id, "y": m.y, "rate": h001.fee_rate(m.fee_schedule),
                      "closed_time": m.closed_time})
c = pd.DataFrame(cands)
print("copias candidatas", len(c), flush=True)
with ThreadPoolExecutor(6) as ex:
    win = list(ex.map(lambda r: trades.fetch(r[0], r[1] + h008.DELAY, r[1] + h008.DELAY + h008.WINDOW,
                                             os.path.join(DATA, "trades_h008_copy")), zip(c.cid, c.ts)))
c["px"] = [h008.copy_price(r, i, t) for r, i, t in zip(win, c.idx, c.ts)]
d = c[c.px.notna()].copy()
pay = np.where(d.idx == 0, d.y, 1 - d.y)
fee = d.rate * d.px * (1 - d.px)
d["pnl"] = pay - d.px - fee
d["ret"] = d.pnl / (d.px + fee)
lo, hi = h001.cluster_bootstrap(d, col="pnl") if len(d) else (np.nan, np.nan)
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
L = ["# H008 G2 — copiar wallets rentables (F: 2025-07→2025-12, T: 2026-01→2026-04-11)", "", f"- commit {commit}",
     f"- formación: {len(fm):,} mercados, {len(tr):,} trades taker, {len(rank):,} wallets elegibles; top {len(top)}",
     f"- PnL F de la top-50: mediana {top.pnl.median():,.0f} USD, n trades mediana {top.n.median():.0f}",
     f"- T: copias candidatas {len(c):,}; con precio real en ventana: {len(d):,} ({d.event_id.nunique():,} eventos, "
     f"{d.wallet.nunique()} wallets)",
     f"- PnL medio por acción {d.pnl.mean()*100:.3f} c (IC95% cluster {lo*100:.3f} … {hi*100:.3f}); retorno medio {d.ret.mean():.3%}",
     f"- precio medio de entrada {d.px.mean():.3f}; acierto {(pay > 0.5).mean():.1%}", ""]
open(os.path.join(ROOT, "reports", "h008_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
