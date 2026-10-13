"""Carga los mercados crudos de Gamma y construye la tabla del universo binario.

Reglas (fijadas antes de ver resultados):
- 2 resultados y tokens CLOB presentes.
- resolución: outcomePrices [1,0] → YES=1; [0,1] → YES=0; cualquier otro → anulado (pago 0.5).
- Se conserva todo (baja liquidez, cancelados). Los filtros de cada hipótesis van aparte.
"""
import glob, gzip, json, os
import pandas as pd

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def _ts(x):
    return pd.to_datetime(x, utc=True, errors="coerce", format="mixed") if x else pd.NaT


def parse(m):
    try:
        outs = json.loads(m.get("outcomes") or "[]")
        toks = json.loads(m.get("clobTokenIds") or "[]")
        px = [float(p) for p in json.loads(m.get("outcomePrices") or "[]")]
    except (ValueError, TypeError):
        return None
    if len(outs) != 2 or len(toks) != 2:
        return None
    if px == [1.0, 0.0]:
        y = 1.0
    elif px == [0.0, 1.0]:
        y = 0.0
    else:
        y = 0.5  # anulado / no resuelto limpio → pago 0.5 (pesimista: se registra aparte)
    ev = (m.get("events") or [{}])[0]
    return {
        "id": int(m["id"]), "condition_id": m.get("conditionId"), "question": m.get("question"), "outcome0": outs[0],
        "token_yes": toks[0], "token_no": toks[1], "y": y,
        "clean": y != 0.5, "start": _ts(m.get("startDate") or m.get("createdAt")),
        "end": _ts(m.get("endDate")), "closed_time": _ts(m.get("closedTime")),
        "event_id": ev.get("id"), "series": ev.get("seriesSlug"),
        "category": m.get("category"), "neg_risk": bool(m.get("negRisk")),
        "volume": float(m.get("volumeNum") or 0), "fees_enabled": bool(m.get("feesEnabled")),
        "fee_type": m.get("feeType"), "fee_schedule": json.dumps(m.get("feeSchedule")) if m.get("feeSchedule") else None,
        "taker_base_fee": m.get("takerBaseFee"), "uma_status": m.get("umaResolutionStatus"),
        "enable_ob": bool(m.get("enableOrderBook")),
    }


def build():
    rows = []
    for f in sorted(glob.glob(os.path.join(DATA, "gamma", "win_*.jsonl.gz"))):
        with gzip.open(f, "rt") as fh:
            for line in fh:
                r = parse(json.loads(line))
                if r:
                    rows.append(r)
    df = pd.DataFrame(rows).drop_duplicates("id")
    df.to_parquet(os.path.join(DATA, "universe_binary.parquet"))
    return df


if __name__ == "__main__":
    d = build()
    print(len(d), d.clean.mean())
