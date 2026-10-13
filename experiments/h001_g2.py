"""H001 G2: exploración SOLO en entrenamiento (closedTime < 2026-04-12).

Variantes (cada una suma 1 al contador global): h ∈ {24h, 7d} con lo/hi = 0.10/0.90.
Uso: python experiments/h001_g2.py   → reports/h001_g2.md
"""
import glob, gzip, json, os, subprocess, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np
import pandas as pd
from pmq import h001
from pmq.universe import DATA

COLS = ["id", "y", "clean", "start", "end", "closed_time", "event_id", "category", "fee_schedule", "volume", "series"]


def load_histories():
    hist = {}
    for f in sorted(glob.glob(os.path.join(DATA, "prices", "h001_*.jsonl.gz"))):
        with gzip.open(f, "rt") as fh:
            for l in fh:
                r = json.loads(l)
                if r["history"] is not None:
                    hist[r["id"]] = r["history"]
    return hist


def main():
    hist = load_histories()
    u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=COLS)
    u = u[u.id.isin(hist.keys())]
    train = u[u.closed_time < h001.HOLDOUT_START]          # el holdout no se toca
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    L = ["# H001 G2 — exploración (solo entrenamiento)", "",
         f"- commit {commit}; mercados con precios en entrenamiento: {len(train):,} "
         f"({train.event_id.nunique():,} eventos)", ""]
    for name, h in [("24h", pd.Timedelta("24h")), ("7d", pd.Timedelta("7D"))]:
        obs = h001.observations(train, hist, h)
        L += [f"## Horizonte {name}", "", f"- observaciones: {len(obs):,}", "", "### Calibración (resueltos limpios)", "",
              h001.calibration(obs).round(4).to_markdown(), ""]
        for mult in (1.0, 2.0):
            tr = h001.trades(obs, cost_mult=mult)
            lo, hi = h001.cluster_bootstrap(tr) if len(tr) else (np.nan, np.nan)
            L += [f"### Estrategia lo=0.10/hi=0.90, costes ×{mult:g}", "",
                  f"- operaciones {len(tr):,} en {tr.event_id.nunique():,} eventos",
                  f"- retorno medio por operación {tr.ret.mean():.4%} (IC95% cluster {lo:.4%} … {hi:.4%})",
                  f"- por lado: " + ", ".join(f"{s}: n={len(g):,} ret={g.ret.mean():.4%}" for s, g in tr.groupby("side")),
                  f"- días medios hasta cierre {tr.days.mean():.2f}", ""]
    out = os.path.join(ROOT, "reports", "h001_g2.md")
    open(out, "w").write("\n".join(L) + "\n")
    print(out)


if __name__ == "__main__":
    main()
