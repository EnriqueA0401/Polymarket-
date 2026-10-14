"""H035 G1 — mercados disputados (Gamma) emparejados con logs DisputePrice on-chain (Polygon).

    PYTHONPATH=src python3 experiments/h035_g1.py      → data/h035/*.parquet, reports/h035_g1.md

Etapas (todas con caché en data/h035/):
1. Gamma: mercados con "disputed" en umaResolutionStatuses (todo el crudo, luego solo entrenamiento:
   closedTime < 2026-04-12; el resto ni se empareja ni se mira).
2. On-chain: logs DisputePrice de OOv2 y MOOv2 desde 2024-01-01 hasta el bloque del 2026-04-12
   (no se leen disputas posteriores al inicio del holdout).
3. Emparejamiento questionID (Gamma) = keccak256(ancillaryData). Primera disputa = hora y propuesta.
4. Verificación del mapeo precio→token con QuestionResolved(settledPrice) de los adaptadores.
"""
import glob, gzip, hashlib, json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h035
from pmq.universe import DATA

D = os.path.join(DATA, "h035")
LOGS = os.path.join(D, "logs")
os.makedirs(D, exist_ok=True)
HO = h001.HOLDOUT_START
START_TS = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp())
CHUNK = 1_000_000
ts_ = lambda x: pd.to_datetime(x, utc=True, errors="coerce", format="mixed") if x else pd.NaT


def scan(f):
    out = []
    for line in gzip.open(f, "rt"):
        if "disputed" not in line:
            continue
        m = json.loads(line)
        st = m.get("umaResolutionStatuses") or ""
        if "disputed" not in st:
            continue
        ev = (m.get("events") or [{}])[0]
        out.append({"id": int(m["id"]), "condition_id": m.get("conditionId"), "question_id": (m.get("questionID") or "").lower(),
                    "neg_risk_request_id": (m.get("negRiskRequestID") or "").lower(), "neg_risk": bool(m.get("negRisk")),
                    "statuses": st, "status": m.get("umaResolutionStatus"), "resolved_by": (m.get("resolvedBy") or "").lower(),
                    "uma_bond": m.get("umaBond"), "uma_end": m.get("umaEndDate"), "closed_time_raw": m.get("closedTime"),
                    "outcome_prices": m.get("outcomePrices"), "outcomes": m.get("outcomes"), "g_event_id": ev.get("id"),
                    "question": m.get("question"), "file": os.path.basename(f)})
    return out


def gamma_disputed():
    p = os.path.join(D, "gamma_disputed.parquet")
    if os.path.exists(p):
        return pd.read_parquet(p)
    rows = []
    with ProcessPoolExecutor(4) as ex:
        for o in ex.map(scan, sorted(glob.glob(os.path.join(DATA, "gamma", "*.jsonl.gz"))), chunksize=20):
            rows += o
    g = pd.DataFrame(rows).drop_duplicates("id")
    g["closed_time"] = [ts_(x) for x in g.closed_time_raw]
    g.to_parquet(p)
    return g


def chain_disputes():
    p = os.path.join(D, "disputes.parquet")
    if os.path.exists(p):
        return pd.read_parquet(p)
    b0 = h035.block_at(START_TS)
    b1 = h035.block_at(int(HO.timestamp())) - 1
    logs = []
    for a in range(b0, b1 + 1, CHUNK):
        logs += h035.get_logs(list(h035.OO), [h035.T_DISPUTE], a, min(a + CHUNK - 1, b1), LOGS, "dispute")
        print("bloque", a, len(logs), flush=True)
    d = pd.DataFrame([h035.decode_dispute(x) for x in logs]).drop_duplicates(["tx", "log_index"])
    d["proposed_price"] = d.proposed_price.astype(str)   # int256 no cabe en int64
    d.to_parquet(p)
    json.dump({"b0": b0, "b1": b1}, open(os.path.join(D, "blocks.json"), "w"))
    return d


def resolved_logs(qids, adapters):
    p = os.path.join(D, "resolved.parquet")
    if os.path.exists(p):
        return pd.read_parquet(p)
    bl = json.load(open(os.path.join(D, "blocks.json")))
    b0, b1 = bl["b0"], bl["b1"]
    qs = sorted(qids)
    logs = []
    for i in range(0, len(qs), 150):
        batch = qs[i:i + 150]
        tag = "resolved_" + hashlib.sha1("".join(batch).encode()).hexdigest()[:10]
        for a in range(b0, b1 + 1, 4 * CHUNK):
            logs += h035.get_logs(adapters, [h035.T_RESOLVED, batch], a, min(a + 4 * CHUNK - 1, b1), LOGS, tag)
        print("resolved", i, len(logs), flush=True)
    r = pd.DataFrame([h035.decode_resolved(x) for x in logs]) if logs else pd.DataFrame(
        columns=["adapter", "qid", "settled_price", "block", "ts"])
    r["settled_price"] = r.settled_price.astype(str)
    r.to_parquet(p)
    return r


g_all = gamma_disputed()
print("gamma disputados", len(g_all), flush=True)
g = g_all[g_all.closed_time < HO].copy()           # entrenamiento; el resto no se usa
n_hold = int((g_all.closed_time >= HO).sum()) + int(g_all.closed_time.isna().sum())
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                    columns=["id", "y", "clean", "event_id", "fee_schedule", "token_yes", "token_no", "start", "end"])
g = g.merge(u, on="id", how="left")
g["in_universe"] = g.y.notna()

dis = chain_disputes()
dis["proposed_price"] = dis.proposed_price.map(int)
adapters = sorted(set(dis.requester))
dis_pm = dis[dis.requester.isin(set(g_all.resolved_by))]
print("disputas on-chain", len(dis), "de adaptadores Polymarket", len(dis_pm), flush=True)

# emparejar: questionID de Gamma (o negRiskRequestID) = keccak256(ancillary)
recs = dis_pm.to_dict("records")
fd_q = h035.first_disputes(recs, set(g.question_id) - {""})
fd_n = h035.first_disputes(recs, set(g.neg_risk_request_id) - {""})
ndisp = dis_pm.groupby("qid").size()


def pick(r):
    d = fd_q.get(r.question_id) or fd_n.get(r.neg_risk_request_id)
    return d


g["fd"] = [pick(r) for r in g.itertuples()]
g["matched"] = g.fd.notna()
g["match_key"] = np.where(g.question_id.isin(fd_q.keys()), "questionID",
                          np.where(g.neg_risk_request_id.isin(fd_n.keys()), "negRiskRequestID", ""))
for k in ("ts", "block", "proposed_price", "oo", "requester", "qid", "req_ts", "tx"):
    g["d_" + k] = [d[k] if d else None for d in g.fd]
g["n_disputes"] = [int(ndisp.get(q, 0)) if q else 0 for q in g.d_qid]
g["side"] = [h035.side_of_price(int(p)) if p is not None else None for p in g.d_proposed_price]
g["d_proposed_price"] = [str(p) if p is not None else None for p in g.d_proposed_price]
g["d_time"] = pd.to_datetime(g.d_ts, unit="s", utc=True)
g["lag_close_h"] = (g.closed_time - g.d_time).dt.total_seconds() / 3600
g = g.drop(columns=["fd"])

# verificación del mapeo con QuestionResolved
qids = set(g.d_qid.dropna())
res = resolved_logs(qids, adapters)
last = res.sort_values("block").groupby("qid").last() if len(res) else pd.DataFrame()
g["settled_price"] = g.d_qid.map(last.settled_price) if len(last) else None
g["settled_side"] = [h035.side_of_price(int(p)) if isinstance(p, str) else None for p in g.settled_price]
g.to_parquet(os.path.join(D, "markets.parquet"))

m = g[g.matched]
mc = m[m.clean.fillna(False).astype(bool) & m.side.notna()]
y_side = np.where(mc.y == 1, 0, 1)
rev = (mc.side.astype(int).values != y_side)
v = m[m.settled_side.notna() & m.clean.fillna(False).astype(bool)]
agree = (v.settled_side.astype(int).values == np.where(v.y == 1, 0, 1)).mean() if len(v) else np.nan
pp = m.d_proposed_price.map(int).map(lambda p: "1 (outcome 0)" if p == h035.ONE else "0 (outcome 1)" if p == 0 else
                                    "0.5 (50-50)" if p == h035.ONE // 2 else "otro")

commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
bl = json.load(open(os.path.join(D, "blocks.json")))
L = ["# H035 G1 — disputas UMA: Gamma ↔ logs on-chain (solo entrenamiento)", "",
     f"- commit {commit}; `PYTHONPATH=src python3 experiments/h035_g1.py`; gamma_disputed.parquet "
     f"{sha(os.path.join(D, 'gamma_disputed.parquet'))}, disputes.parquet {sha(os.path.join(D, 'disputes.parquet'))}",
     f"- Fuente on-chain: eth_getLogs (RPC público Tenderly, Polygon) del evento DisputePrice en OOv2 "
     f"{h035.OO[0]} y MOOv2 {h035.OO[1]}, bloques {bl['b0']:,}–{bl['b1']:,} (2024-01-01 → 2026-04-12 00:00 UTC, "
     "nada del periodo holdout). Hora de disputa = blockTimestamp del log.",
     "", "## Universo Gamma", "",
     f"- mercados con 'disputed' en umaResolutionStatuses (todo el crudo): {len(g_all):,} en {g_all.g_event_id.nunique():,} eventos",
     f"- con closedTime ≥ 2026-04-12 o sin cerrar (holdout / no usados): {n_hold:,}",
     f"- **entrenamiento (closedTime < 2026-04-12): {len(g):,} mercados en {g.g_event_id.nunique():,} eventos**; "
     f"en universe_binary: {int(g.in_universe.sum()):,}; resolución limpia: {int(g.clean.fillna(False).astype(bool).sum()):,}",
     f"- closedTime de entrenamiento: {g.closed_time.min():%Y-%m-%d} … {g.closed_time.max():%Y-%m-%d} "
     "(Gamma solo rellena umaResolutionStatuses desde ~2025-03; disputas anteriores no entran en el universo)",
     f"- adaptador (resolvedBy): " + "; ".join(f"{a[:10]}… {n}" for a, n in g.resolved_by.value_counts().items()),
     "", "## Emparejamiento on-chain", "",
     f"- logs DisputePrice en el rango: {len(dis):,}; de adaptadores de Polymarket: {len(dis_pm):,} "
     f"({dis_pm.qid.nunique():,} questionIDs)",
     f"- **mercados de entrenamiento con disputa on-chain encontrada: {len(m):,} / {len(g):,} "
     f"({len(m) / max(len(g), 1):.1%}) en {m.g_event_id.nunique():,} eventos**; clave: "
     + ", ".join(f"{k} {n}" for k, n in m.match_key.value_counts().items()),
     "- sin emparejar por adaptador: " + "; ".join(f"{a[:10]}… {n}" for a, n in g[~g.matched].resolved_by.value_counts().items()),
     f"- disputas por questionID emparejado: " + ", ".join(f"{k}: {n}" for k, n in m.n_disputes.value_counts().sort_index().items()),
     "- propuesta disputada (primera disputa): " + "; ".join(f"{k}: {n}" for k, n in pp.value_counts().items()),
     f"- horas desde la primera disputa hasta closedTime: mediana {m.lag_close_h.median():.1f}, p10 "
     f"{m.lag_close_h.quantile(.1):.1f}, p90 {m.lag_close_h.quantile(.9):.1f}; disputas posteriores a closedTime: "
     f"{int((m.lag_close_h < 0).sum())}",
     f"- verificación precio→token (QuestionResolved del adaptador, último por questionID): {len(v):,} mercados limpios "
     f"con settledPrice; concordancia con el resultado de Gamma {agree:.1%}",
     "", "## Reversión (resultado final ≠ propuesta disputada)", "",
     f"- mercados emparejados, resolución limpia y propuesta 0/1: {len(mc):,} en {mc.g_event_id.nunique():,} eventos",
     f"- **tasa de reversión: {rev.mean():.1%}** (la propuesta original se mantiene en {1 - rev.mean():.1%})",
     "- por propuesta: " + "; ".join(f"propuesto idx {s}: n={int((mc.side == s).sum())}, reversión "
                                       f"{rev[(mc.side == s).values].mean():.1%}" for s in (0, 1)),
     f"- por adaptador negRisk: " + "; ".join(f"negRisk={k}: n={int((mc.neg_risk == k).sum())}, reversión "
                                              f"{rev[(mc.neg_risk == k).values].mean():.1%}" for k in (False, True)),
     f"- anulados / 50-50 entre los emparejados: {int((~m.clean.fillna(False).astype(bool)).sum())}",
     "", "## Notas", "",
     "1. Solo la PRIMERA disputa de cada questionID; si el adaptador reinicia la pregunta, la segunda propuesta "
     "comparte questionID y una segunda disputa va al DVM.",
     "2. Mercados de entrenamiento = closedTime < 2026-04-12. Disputados antes del corte pero cerrados después "
     "quedan fuera (pertenecen al holdout por la regla de closedTime).",
     ]
open(os.path.join(ROOT, "reports", "h035_g1.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
