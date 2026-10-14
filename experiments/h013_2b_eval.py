"""H013 etapa 2b: evaluación del paper trading. python experiments/h013_2b_eval.py → reports/h013_2b.md
Mercados resueltos: PnL a resolución (Gamma). No resueltos: valoración a mid (solo informativa)."""
import json, os, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd, requests
from pmq import h013live as L

st = json.load(open(L.STATE))
log = pd.read_csv(os.path.join(L.LIVE, "log.csv"))
last_mid = log.dropna(subset=["mid"]).groupby("cid").mid.last()
rows = []
for cid, m in st["markets"].items():
    g = requests.get("https://gamma-api.polymarket.com/markets", params={"condition_ids": cid}).json()
    y, res = np.nan, False
    if g and g[0].get("closed"):
        px = [float(p) for p in json.loads(g[0].get("outcomePrices") or "[]")]
        y = 1.0 if px == [1.0, 0.0] else 0.0 if px == [0.0, 1.0] else 0.5
        res = True
    mark = y if res else last_mid.get(cid, np.nan)
    pnl = L.settle(m, mark) if pd.notna(mark) else np.nan
    days = (min(pd.Timestamp(m["end"]), pd.Timestamp(st["last"], unit="s", tz="UTC")) - pd.Timestamp(st["created"])).total_seconds() / 86400
    rows.append({"cid": cid, "q": m["q"][:60], "resolved": res, "rate": m["rate"], "reward": m["reward"], "pnl": pnl,
                 "total": pnl + m["reward"], "capital": m["max_capital"], "days": max(days, 1 / 24),
                 "fills": m["fills_bid"] + m["fills_ask"]})
d = pd.DataFrame(rows)
d["yield_day"] = d.total / d.capital.replace(0, np.nan) / d.days
rng = np.random.default_rng(0)
def boot(x, n=4000):
    x = x.dropna().values
    if len(x) < 5:
        return (np.nan, np.nan)
    m = [x[rng.integers(0, len(x), len(x))].sum() for _ in range(n)]
    return np.percentile(m, 2.5), np.percentile(m, 97.5)
r = d[d.resolved]
lo, hi = boot(r.total)
Lines = ["# H013 etapa 2b — paper trading maker con recompensas", "",
         f"- inicio {st['created']}; último paso {pd.Timestamp(st['last'], unit='s')}; candidatos {st['candidates']}; mercados {len(d)}",
         f"- resueltos {len(r)}: Σ recompensas {r.reward.sum():.2f} USD, Σ PnL {r.pnl.sum():.2f} USD, Σ total {r.total.sum():.2f} USD "
         f"(IC95% {lo:.2f} … {hi:.2f}); rendimiento/día mediano {r.yield_day.median():.3%}",
         f"- no resueltos (valorados a mid, informativo): {int((~d.resolved).sum())}; Σ total {d[~d.resolved].total.sum():.2f} USD",
         f"- fills totales {int(d.fills.sum())}; capital máx. mediano {d.capital.median():.2f} USD", "",
         d.sort_values("total")[["q", "resolved", "rate", "reward", "pnl", "total", "capital", "fills"]].round(2).to_markdown(index=False)]
open(os.path.join(ROOT, "reports", "h013_2b.md"), "w").write("\n".join(Lines) + "\n")
print("\n".join(Lines[:6]))
