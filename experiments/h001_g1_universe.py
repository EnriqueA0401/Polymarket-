"""H001 G1: resumen del universo y del subconjunto elegible. Salida: reports/h001_g1_universe.md"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
from pmq.universe import DATA
from pmq.fetch_prices import targets

u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                    columns=["id", "y", "clean", "start", "end", "closed_time", "event_id", "enable_ob",
                             "category", "series", "volume", "fee_schedule"])
t = targets(u)
L = ["# H001 G1 — universo", "", f"- Mercados binarios cerrados: {len(u):,}",
     f"- Resolución limpia (1/0): {u.clean.mean():.4f}; anulados/otros: {(~u.clean).sum():,}",
     f"- Sin endDate: {u.end.isna().sum():,}; sin closedTime: {u.closed_time.isna().sum():,}",
     f"- Con orderbook CLOB: {u.enable_ob.sum():,}",
     f"- Elegibles H001 (existían en end−24h, no cerrados antes de end−7d): {len(t):,} "
     f"en {t.event_id.nunique():,} eventos", "",
     "## Elegibles por año de cierre", "", "| año | mercados | eventos | % limpios |", "|---|---|---|---|"]
yr = t.assign(yr=t.closed_time.dt.year.astype("Int64")).groupby("yr").agg(n=("id", "size"), ev=("event_id", "nunique"), c=("clean", "mean"))
L += [f"| {int(k)} | {r.n:,} | {r.ev:,} | {r.c:.3f} |" for k, r in yr.iterrows()]
ho = t.closed_time >= pd.Timestamp("2026-04-12", tz="UTC")
L += ["", f"- Holdout (closedTime ≥ 2026-04-12): {ho.sum():,} mercados, {t[ho].event_id.nunique():,} eventos",
      f"- Entrenamiento: {(~ho).sum():,} mercados, {t[~ho].event_id.nunique():,} eventos", "",
      "## Retraso cierre − endDate (elegibles, horas)", "",
      (((t.closed_time - t.end).dt.total_seconds() / 3600).describe(percentiles=[.01, .1, .5, .9, .99]).round(2).to_string())]
open(os.path.join(os.path.dirname(__file__), "..", "reports", "h001_g1_universe.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L[:12]))
