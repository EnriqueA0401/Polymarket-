"""H023 G1: emparejamiento PM ↔ Kalshi (NFL/NBA/MLB), verificación de resoluciones y cobertura de datos
(trades de Kalshi pre-partido; trades PM alrededor de cada movimiento candidato de Kalshi).
Solo entrenamiento (closedTime PM < 2026-04-12); el holdout no se descarga.
python experiments/h023_g1.py → reports/h023_g1.md, data/h023/matches.parquet, data/h023/cands.parquet"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h023 as H, h001, trades
from pmq.universe import DATA

PM_CACHE = os.path.join(DATA, "trades_h023")
pm_path = os.path.join(H.CACHE, "pm_moneyline.parquet")
pm = pd.read_parquet(pm_path) if os.path.exists(pm_path) else H.extract_pm(pm_path)
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                    columns=["id", "condition_id", "y", "clean", "closed_time", "event_id", "fee_schedule"])
pm = pm.merge(u, on="id", how="inner")
n_all = len(pm)
first_k = min(pd.Timestamp(m["open_time"]) for s, _ in H.LEAGUES.values() for m in H.k_markets(s))
pm = pm[pm.game_start >= first_k - pd.Timedelta("1D")]
n_kper = len(pm)
hold = pm[~(pm.closed_time < H.HOLDOUT_START)]
pm = pm[pm.closed_time < H.HOLDOUT_START].copy()

kev = [e for lg, (s, _) in H.LEAGUES.items() for e in H.k_events(H.k_markets(s), lg)]
m = H.match(pm, kev).merge(pm[["id", "condition_id", "y", "clean", "closed_time", "event_id", "fee_schedule",
                                "game_start", "question", "series"]], on="id")
ok = m[m.status == "ok"].copy()
ok["k_y0"] = ok.k_result0.map(H.k_y)
ok["agree"] = ok.clean & ok.k_y0.notna() & (ok.y == ok.k_y0)
ok["mismatch"] = ok.clean & ok.k_y0.notna() & (ok.y != ok.k_y0)
dup = ok.k_event.duplicated(keep=False)          # varios mercados PM ↔ un evento Kalshi → excluir
ok["dup"] = dup
g = ok[ok.agree & ~ok.dup].copy()
g["season"] = [gs.year if lg == "MLB" else (gs.year if gs.month >= 7 else gs.year - 1)
               for lg, gs in zip(g.league, g.game_start)]
g["gs"] = [int(x.timestamp()) for x in g.game_start]
g["rate"] = [h001.fee_rate(x) for x in g.fee_schedule]

# ---- Kalshi: trades pre-partido (desde 14 días antes hasta el inicio) ----
def kfetch(r):
    try:
        return H.k_trades(r.k_ticker0, r.gs - 14 * 86400, r.gs)
    except RuntimeError:
        return None
with ThreadPoolExecutor(4) as ex:                   # ritmo global limitado en H.k_get
    kt = list(ex.map(kfetch, list(g.itertuples())))
print("kalshi ok", flush=True)
g["k_fail"] = [x is None for x in kt]
g["k_n"] = [len(x) if x else 0 for x in kt]

# ---- candidatos (solo condición de Kalshi), real y placebo (−600 s) ----
rows = []
for r, tr in zip(g.itertuples(), kt):
    t, p = H.k_series(tr or [])
    for shift in (0, -600):
        for tc, dk in H.k_candidates(t, p, r.gs, shift=shift):
            rows.append({"id": r.id, "shift": shift, "t": tc, "dk": dk})
cands = pd.DataFrame(rows, columns=["id", "shift", "t", "dk"])

# ---- PM: trades en ventanas [t−WIN−LOOKBACK, t+ENTRY_END] fusionadas por partido ----
def windows(ts):
    iv = sorted((int(np.floor(t - H.WIN - H.PM_LOOKBACK)), int(np.ceil(t + H.ENTRY_END))) for t in ts)
    out = []
    for a, b in iv:
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out

def pm_fetch(cid, a, b):
    d = trades.fetch(cid, a, b, PM_CACHE)
    if d is not None and len(d) >= 10000 and b - a > 120:
        mid = (a + b) // 2
        x, y = pm_fetch(cid, a, mid), pm_fetch(cid, mid + 1, b)
        d = None if x is None or y is None else x + y
    return d

cid = dict(zip(g.id, g.condition_id))
jobs = [(i, a, b) for i, grp in cands.groupby("id") for a, b in windows(grp.t.values)]
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda j: pm_fetch(cid[j[0]], j[1], j[2]), jobs))
wj = pd.DataFrame([{"id": i, "a": a, "b": b, "fail": r is None, "n": len(r) if r else 0}
                   for (i, a, b), r in zip(jobs, res)])
wj.to_parquet(os.path.join(H.CACHE, "pm_windows.parquet"))
g.drop(columns=["fee_schedule"]).to_parquet(os.path.join(H.CACHE, "matches.parquet"))
cands.to_parquet(os.path.join(H.CACHE, "cands.parquet"))

# ---- informe ----
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
c0 = cands[cands["shift"] == 0]
by = g.groupby(["league", "season"]).agg(partidos=("id", "size"), con_trades_kalshi=("k_n", lambda s: int((s > 0).sum())),
                                         trades_kalshi_mediana=("k_n", "median"))
by["con_candidato_kalshi"] = [c0[c0.id.isin(g[(g.league == l) & (g.season == s)].id)].id.nunique() for l, s in by.index]
st = m.groupby(["league", "status"]).size().unstack(fill_value=0)
L = ["# H023 G1 — emparejamiento Polymarket ↔ Kalshi (NFL/NBA/MLB, ganador del partido)", "",
     f"- commit {commit}; datos: Gamma crudo (data/gamma), Kalshi API pública (data/h023), Data API PM (data/trades_h023)",
     f"- mercados moneyline PM extraídos (series NFL/NBA/MLB, 'A vs. B', gameStartTime): {n_all:,}; "
     f"con inicio ≥ primer mercado de Kalshi ({first_k.date()}): {n_kper:,}",
     f"- holdout (closedTime ≥ 2026-04-12 o sin cerrar) apartado sin tocar: {len(hold):,}; entrenamiento: {len(pm):,}",
     f"- eventos Kalshi (dos mercados, equipos reconocidos): {len(kev):,}",
     "", "## Estado del emparejamiento (entrenamiento)", "", st.to_markdown(), "",
     "## Resoluciones", "",
     f"- emparejados ok: {len(ok):,}; PM limpio y Kalshi yes/no: {int((ok.clean & ok.k_y0.notna()).sum()):,}",
     f"- **coinciden: {int(ok.agree.sum()):,}; discrepan: {int(ok.mismatch.sum()):,}** (excluidas)",
     f"- PM anulado/no limpio: {int((~ok.clean).sum()):,}; Kalshi sin yes/no (empate/cancelado): {int(ok.k_y0.isna().sum()):,}",
     f"- eventos Kalshi con >1 mercado PM (excluidos): {int(ok.dup.sum()):,}",
     f"- **partidos utilizables: {len(g):,}**", "",
     "## Por liga y temporada", "", by.to_markdown(), "",
     "## Cobertura de datos", "",
     f"- descargas Kalshi fallidas: {int(g.k_fail.sum())}; partidos sin trades Kalshi pre-partido: {int((g.k_n == 0).sum()):,}",
     f"- candidatos Kalshi (|ΔK| ≥ 0.05 en 2 min, t+5 min ≤ inicio; sin refractario): real {len(c0):,} en "
     f"{c0.id.nunique():,} partidos; placebo −10 min {int((cands['shift'] == -600).sum()):,}",
     f"- ventanas PM descargadas: {len(wj):,}; fallidas: {int(wj.fail.sum()) if len(wj) else 0}; "
     f"con ≥10 000 filas (troceadas): {int((wj.n >= 10000).sum()) if len(wj) else 0}",
     f"- comisión: feeSchedule del mercado si existe, si no 0.07 (regla de reports/costs.md); "
     f"rates observados: {g.rate.value_counts().to_dict()}",
     "", "## Discrepancias de resolución (hasta 20)", "",
     ok[ok.mismatch].head(20)[["id", "question", "game_start", "k_event", "y", "k_result0"]].to_markdown(index=False),
     "", "## Muestra de emparejamientos (revisión manual)", "",
     g.sample(min(25, len(g)), random_state=0)[["question", "game_start", "k_event", "k_ticker0", "y", "k_result0"]].to_markdown(index=False),
     "", "## Decisiones de G1 (fijadas antes de ver precios)", "",
     "- Emparejamiento: (liga, fecha ET de gameStartTime de PM, conjunto de equipos) ↔ (fecha del ticker de Kalshi, "
     "códigos de equipo → nombre completo por tabla `TEAMS` en src/pmq/h023.py). Nombres PM leídos de la descripción "
     "('If <equipo> wins, … resolve to “<outcome>”'). Coincidencias múltiples (dobles jornadas MLB) → excluidas.",
     "- Mercado de Kalshi usado: el del equipo outcome0 de PM.",
     "- Inicio del partido: gameStartTime de Gamma (programado, conocido de antemano)."]
open(os.path.join(ROOT, "reports", "h023_g1.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L[:30]))
