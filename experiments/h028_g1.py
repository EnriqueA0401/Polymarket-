"""H028 G1 — universo, reglas, historial de sorpresas (Yahoo) y concordancia con la resolución.

Solo entrenamiento (closedTime < 2026-04-12). Requiere data/h028/raw_markets.jsonl.gz (extraído de
data/gamma) y la caché de Yahoo en data/h028/yahoo/ (se descarga si falta).
python experiments/h028_g1.py → reports/h028_g1.md y data/h028/markets.parquet
"""
import gzip, glob, json, os, subprocess, sys, hashlib
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h028
from pmq.universe import DATA

OUT = os.path.join(DATA, "h028")
RAW = os.path.join(OUT, "raw_markets.jsonl.gz")
YCACHE = os.path.join(OUT, "yahoo")

u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                    columns=["id", "condition_id", "question", "y", "clean", "end", "closed_time", "event_id", "fee_schedule"])
q = u.question.str.lower()
allm = u[q.str.contains("earnings") & q.str.contains("beat")].copy()
n_all, n_hold = len(allm), int((allm.closed_time >= h001.HOLDOUT_START).sum())
m = allm[allm.closed_time < h001.HOLDOUT_START].copy()   # holdout intacto

if not os.path.exists(RAW):   # extraer descripciones de Gamma (por día de endDate)
    ids = set(allm.id.astype(int)); rows = []
    for d in sorted(set(allm.end.dt.strftime("%Y-%m-%d"))):
        for f in glob.glob(os.path.join(DATA, "gamma", f"win_{d}.jsonl.gz")):
            for line in gzip.open(f, "rt"):
                x = json.loads(line)
                if int(x["id"]) in ids:
                    rows.append({k: x.get(k) for k in ("id", "question", "description", "endDate", "startDate", "closedTime")})
    with gzip.open(RAW, "wt") as f:
        for x in rows:
            f.write(json.dumps(x) + "\n")
raw = {int(json.loads(l)["id"]): json.loads(l) for l in gzip.open(RAW, "rt")}
m["desc"] = [raw.get(int(i), {}).get("description") or "" for i in m.id]
m["ticker"] = [h028.parse_ticker(qq, d) for qq, d in zip(m.question, m.desc)]
m["strike"] = [h028.parse_strike(d) for d in m.desc]
m["est_date"] = [h028.parse_est_date(d) for d in m.desc]
m["rate"] = [h001.fee_rate(x) for x in m.fee_schedule]
m["tmpl_new"] = m.desc.str.contains("SeekingAlpha")
m["tmpl_45d"] = m.desc.str.contains("45 calendar days")

rows = []
for r in m.itertuples():
    h = h028.yahoo_history(r.ticker, YCACHE) if r.ticker else None
    anchor = r.est_date.tz_convert("UTC") if r.est_date is not None else r.end
    rep = h028.match_report(h, anchor)
    rt = rep["date"] if rep is not None else pd.NaT
    t = h028.decision_time(rt, r.end)
    p, n, k = h028.base_rate(h, t)
    rows.append({"id": r.id, "hist_len": 0 if h is None else int(h.beat.notna().sum()),
                 "report_time": rt, "y_est": rep["estimate"] if rep is not None else np.nan,
                 "y_rep": rep["reported"] if rep is not None else np.nan,
                 "beat_src": rep["beat"] if rep is not None else np.nan,
                 "t": t, "prob": p, "n_hist": n, "k_hist": k})
m = m.merge(pd.DataFrame(rows), on="id")
m["report_day"] = [(rt if pd.notna(rt) else e).tz_convert("America/New_York").strftime("%Y-%m-%d")
                   for rt, e in zip(m.report_time, m.end)]
m["beat_strike"] = [h028.beat_flag(rp, s) if s is not None else np.nan for rp, s in zip(m.y_rep, m.strike)]
m["dt_end_h"] = (m.end - m.report_time).dt.total_seconds() / 3600
m["t_after_close"] = m.t >= m.closed_time
m.drop(columns=["desc"]).to_parquet(os.path.join(OUT, "markets.parquet"))

# ---------- informe ----------
c = m[m.clean]
mt = m[m.report_time.notna()]
ag = c[c.beat_src.notna()]
ags = c[c.beat_strike.notna()]
dis = ag[ag.beat_src != ag.y]
cons = mt[mt.strike.notna() & mt.y_est.notna()]
cons_diff = (cons.strike - cons.y_est).abs()
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
uh = hashlib.sha256(open(os.path.join(DATA, "universe_binary.parquet"), "rb").read()).hexdigest()[:12]
L = ["# H028 G1 — Mercados \"beat quarterly earnings\" (solo entrenamiento)", "",
     f"- commit {commit}; universe_binary.parquet sha256[:12] {uh}; fuente de sorpresas: Yahoo Finance (yfinance get_earnings_dates), caché data/h028/yahoo/",
     "", "## Universo",
     f"- Mercados con 'earnings' y 'beat' en la pregunta: {n_all:,} (holdout closedTime ≥ 2026-04-12: {n_hold:,}, NO tocados).",
     f"- Entrenamiento: {len(m):,} mercados; limpios (YES/NO): {int(m.clean.sum()):,}; anulados: {int((~m.clean).sum())}.",
     f"- Empresas (tickers): {m.ticker.nunique():,}; sin ticker: {int(m.ticker.isna().sum())}; "
     f"fechas de informe distintas (clusters): {m.report_day.nunique():,}; eventos Gamma: {m.event_id.nunique():,}.",
     f"- endDate: {m.end.min():%Y-%m-%d} … {m.end.max():%Y-%m-%d}. Tasa YES en entrenamiento: {c.y.mean():.3f} (n={len(c):,}).",
     f"- Comisión: ningún mercado expone feeSchedule → regla pesimista 0.07 (reports/costs.md).",
     "", "## Regla de resolución (descripciones de Gamma)",
     f"- Plantilla estándar ({int(m.tmpl_new.sum())} de {len(m)}): YES si el EPS non-GAAP publicado (documentos oficiales; si no, "
     "SeekingAlpha; si no, GAAP) es estrictamente MAYOR que el consenso 'Street' fijado al crear el mercado; redondeo a céntimos; "
     "empate = NO; si no publica en 45 días desde la fecha estimada = NO; reexpresiones posteriores no cuentan.",
     f"- Plantilla antigua ({int((~m.tmpl_new).sum())}): mismo criterio (non-GAAP diluido > consenso, empate = NO) con la nota de prensa como fuente.",
     f"- Umbral (strike) extraído de la descripción: {int(m.strike.notna().sum())} de {len(m)}; fecha estimada del informe: {int(m.est_date.notna().sum())}.",
     "- Momento: endDate ≈ hora del informe (13–14 UTC antes de apertura, 21–22 UTC tras cierre); la resolución llega horas después.",
     "", "## Cobertura del historial de sorpresas (Yahoo)",
     f"- Tickers con historial en Yahoo: {m[m.hist_len > 0].ticker.nunique()} de {m.ticker.nunique()}.",
     f"- Mercados con informe de Yahoo emparejado (± {h028.MATCH_DAYS} días de la fecha estimada): {len(mt):,} de {len(m):,}.",
     f"- Trimestres previos usados (n, informes con fecha < t): media {m.n_hist.mean():.2f}; n = 8: {(m.n_hist == 8).mean():.1%}; "
     f"n = 0: {(m.n_hist == 0).mean():.1%}; n ≥ 4: {(m.n_hist >= 4).mean():.1%}.",
     f"- Tasa de batida histórica (k/n agregada): {m.k_hist.sum() / max(m.n_hist.sum(), 1):.3f}; prob. media del modelo {m.prob.mean():.3f}; "
     f"desv. típica {m.prob.std():.3f}.",
     f"- Diferencia hora del informe (Yahoo) − endDate: mediana {(-m.dt_end_h).median():+.1f} h; |dif| > 24 h: {int((m.dt_end_h.abs() > 24).sum())} mercados.",
     f"- t ≥ closedTime (mercado ya cerrado en t): {int(m.t_after_close.sum())}; hora Yahoo > closedTime: "
     f"{int((m.report_time > m.closed_time).sum())}; sin emparejar con closedTime < endDate: "
     f"{int((m.report_time.isna() & (m.closed_time < m.end)).sum())}. En los {int((m.dt_end_h.abs() > 24).sum())} casos con "
     "|dif| > 24 h la fecha de Yahoo cuadra con closedTime (la fecha estimada del mercado estaba desfasada).",
     "", "## Concordancia fuente vs resolución del mercado (mercados limpios)",
     f"- Batida Yahoo (reportado > estimado Yahoo) vs resolución: {(ag.beat_src == ag.y).mean():.3f} (n={len(ag):,}); "
     f"YES-mercado/no-batida-Yahoo {int(((ag.y == 1) & (ag.beat_src == 0)).sum())}, NO-mercado/batida-Yahoo {int(((ag.y == 0) & (ag.beat_src == 1)).sum())}.",
     f"- Reportado Yahoo > strike del mercado vs resolución: {(ags.beat_strike == ags.y).mean():.3f} (n={len(ags):,}).",
     f"- |strike − estimado Yahoo|: mediana {cons_diff.median():.3f} USD; > 0.02: {(cons_diff > 0.02).mean():.1%} (n={len(cons):,}); "
     f"strike > estimado Yahoo en {(cons.strike > cons.y_est).mean():.1%}, < en {(cons.strike < cons.y_est).mean():.1%}.",
     f"- Tasa de batida Yahoo en estos mismos informes: {ag.beat_src.mean():.3f}; tasa YES del mercado: {ag.y.mean():.3f}.",
     "", "## Notas G1",
     "- La tasa base usa solo informes de Yahoo con fecha estrictamente < t (test anti-lookahead en tests/test_h028.py).",
     "- El consenso de Yahoo no es el mismo que el 'Street consensus' usado como strike: la tasa base se mide contra el consenso de Yahoo.",
     "- Las horas de Yahoo para informes antiguos pueden ser aproximadas; t = hora Yahoo − 24 h deja margen ≥ 15 h salvo error de día.",
     ""]
open(os.path.join(ROOT, "reports", "h028_g1.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
