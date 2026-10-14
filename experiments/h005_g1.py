"""H005 G1: emparejamiento PM ↔ football-data y verificación de resoluciones (sin precios).
python experiments/h005_g1.py → reports/h005_g1.md, data/h005_matches.parquet"""
import os, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import pandas as pd
from pmq import football as F
from pmq.universe import DATA

u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                    columns=["id", "question", "series", "y", "clean", "closed_time", "event_id", "condition_id", "end", "start"])
pm = u[u.series.isin(F.SERIES_TO_LEAGUE)]
pm = pm[pm.question.str.match(F.Q_RE.pattern, na=False)]
fd = F.load_fd()
m = F.match_markets(pm, fd)
ok0 = m[m.status == "ok"]
ok = F.consistent(ok0).merge(u[["id", "y", "clean", "closed_time", "event_id", "condition_id", "end"]], on="id")
ok["fd_y"] = (ok.FTR == ok.side).astype(float)
cl = ok[ok.clean]
mism = cl[cl.y != cl.fd_y]
ok.to_parquet(os.path.join(DATA, "h005_matches.parquet"))
L = ["# H005 G1 — emparejamiento Polymarket ↔ football-data", "",
     f"- partidos football-data cargados: {len(fd):,}",
     f"- mercados PM candidatos (series mapeadas, 'Will X win on D?'): {len(pm):,}",
     "- estado: " + ", ".join(f"{k}: {v:,}" for k, v in m.status.value_counts().items()),
     f"- descartados por inconsistencia de nombre modal: {len(ok0) - len(ok):,}",
     f"- emparejados con resolución limpia: {len(cl):,}; resolución PM ≠ resultado football-data: {len(mism):,} "
     f"({len(mism)/max(len(cl),1):.2%})",
     f"- kickoff − endDate (horas): mediana {((ok.end - ok.kickoff).dt.total_seconds()/3600).median():.2f}",
     "", "## Por liga", "", ok.groupby("league").agg(n=("id", "size"), errores=("fd_y", lambda s: 0)).drop(columns="errores").to_markdown(),
     "", "## Muestra de emparejamientos (revisión manual)", "",
     ok.sample(min(30, len(ok)), random_state=0)[["team", "fd_home", "fd_away", "side", "score"]].to_markdown(index=False),
     "", "## Discrepancias de resolución (hasta 20)", "",
     mism.head(20)[["team", "fd_home", "fd_away", "side", "FTR", "y"]].to_markdown(index=False)]
open(os.path.join(ROOT, "reports", "h005_g1.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L[:8]))
