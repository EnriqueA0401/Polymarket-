"""H008 diagnóstico: PnL en T de las top wallets con SUS precios (persistencia de habilidad).
Usa la caché de experiments/h008.py. → se añade a reports/h008_g2.md"""
import glob, gzip, json, os, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h008
from pmq.universe import DATA

u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=["condition_id", "y", "event_id"]).drop_duplicates("condition_id").set_index("condition_id")
rows = []
for f in glob.glob(os.path.join(DATA, "trades_h008_user", "*.json.gz")):
    w = os.path.basename(f).split("_")[0]
    for x in json.load(gzip.open(f, "rt")):
        if x["conditionId"] in u.index:
            m = u.loc[x["conditionId"]]
            pay = m.y if x["outcomeIndex"] == 0 else 1 - m.y
            px = float(x["price"])
            if x["side"] == "BUY":
                rows.append((w, m.event_id, pay - px, float(x["size"]) * (pay - px)))
d = pd.DataFrame(rows, columns=["wallet", "event_id", "pnl", "usd"])
lo, hi = h001.cluster_bootstrap(d, col="pnl")
L = ["", "## Diagnóstico: compras de las top wallets en T a SU precio", "",
     f"- compras {len(d):,} ({d.wallet.nunique()} wallets, {d.event_id.nunique():,} eventos)",
     f"- PnL medio por acción {d.pnl.mean()*100:.3f} c (IC95% cluster {lo*100:.3f} … {hi*100:.3f}); PnL total {d.usd.sum():,.0f} USD",
     f"- wallets con PnL>0 en T: {(d.groupby('wallet').usd.sum() > 0).mean():.0%}"]
open(os.path.join(ROOT, "reports", "h008_g2.md"), "a").write("\n".join(L) + "\n")
print("\n".join(L))
