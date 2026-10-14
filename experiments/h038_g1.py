"""H038 G1 — universo de Kalshi (solo ENTRENAMIENTO: liquidados < 2026-04-12), cobertura de trades
y tabla de calibración en t = cierre programado − 24 h.

Regenerar (con la caché de data/h038 ya descargada):
  PYTHONPATH=src python3 experiments/h038_fetch.py series
  PYTHONPATH=src python3 experiments/h038_fetch.py universe
  PYTHONPATH=src python3 experiments/h038_fetch.py sample 40000
  PYTHONPATH=src python3 experiments/h038_fetch.py trades
  PYTHONPATH=src python3 experiments/h038_g1.py
"""
import hashlib, json, os, subprocess
import numpy as np
import pandas as pd

from pmq import h038

OUT = os.path.join(os.path.dirname(__file__), "..", "reports", "h038_g1.md")
C = h038.CACHE


def md(df, floatfmt=3):
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind == "f":
            df[c] = df[c].round(floatfmt)
    return df.to_markdown()


def main():
    uni = pd.read_parquet(os.path.join(C, "universe_train.parquet"))
    meta = pd.read_csv(os.path.join(C, "series_meta.csv"))
    ser = pd.DataFrame(json.load(open(os.path.join(C, "series.json"))))
    assert (pd.to_datetime(uni.settlement_ts.fillna(uni.close_time), utc=True, format="mixed")
            < h038.HOLDOUT_START).all(), "holdout filtrado en el universo"
    uni["settle"] = pd.to_datetime(uni.settlement_ts.fillna(uni.close_time), utc=True, format="mixed")
    uni["month"] = uni.settle.dt.strftime("%Y-%m")
    uni["binary"] = uni.market_type == "binary"
    uni["vol_pos"] = uni.volume_fp.astype(float) > 0
    samp = uni[uni.sampled & uni.eligible]
    obs = h038.build_obs(samp)
    obs["has_p"] = obs.p_yes.notna()
    obs["fresh"] = obs.n_win.fillna(0) > 0
    obs["signal"] = obs.side.notna()
    obs["exec"] = obs.exec_price.notna()
    obs.to_parquet(os.path.join(C, "obs_train.parquet"))

    L = ["# H038 G1 — Universo Kalshi, cobertura y calibración (solo entrenamiento)", ""]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        commit = "?"
    h = hashlib.sha256(pd.util.hash_pandas_object(uni[["ticker", "result", "t"]], index=False).values).hexdigest()[:16]
    L += [f"Commit base: `{commit}` · hash universo (ticker,result,t): `{h}` · "
          f"generado {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC", ""]

    L += ["## Fuente y filtros", "",
          f"- Series en /series: {len(ser)}; recorridas (sin KXMVE* combos): {len(meta)}; "
          f"alta frecuencia (15 min/horaria) descartadas por inelegibilidad estructural "
          f"(ningún mercado de la página más reciente abre ≥ 25 h antes de su cierre previsto): "
          f"{int(meta.skipped_structural.sum())}.",
          f"- Mercados históricos (archivados, /historical/markets) leídos: entrenamiento "
          f"{int(meta.n_train.sum())}; descartados sin guardar por liquidar ≥ 2026-04-12 (holdout): "
          f"{int(meta.n_holdout_dropped.sum())}.",
          f"- Rango de liquidación en entrenamiento: {uni.settle.min():%Y-%m-%d} → {uni.settle.max():%Y-%m-%d}. "
          "Las series legado (INX, FED, HIGHNY…) devuelven 0 mercados en la API histórica: el historial "
          "público empieza con las series KX*. Limitación documentada (no hay otra fuente pública).",
          f"- Resultados: {uni.result.fillna('∅').value_counts().to_dict()}", ""]

    L += ["## Elegibilidad en t = cierre programado − 24 h", "",
          "Cierre programado = `expected_expiration_time` (fijado al listar); `close_time` solo si falta "
          "(se reescribe con el cierre real en cierres anticipados → lookahead). Elegible = binario, "
          "volumen > 0, `open_time` < t y `close_time` > t − 1 h.", ""]
    ref_from_close = uni.expected_expiration_time.isna().mean()
    eet = pd.to_datetime(uni.expected_expiration_time, utc=True, format="mixed")
    odd = ((eet.dt.second != 0) | (eet.dt.minute % 5 != 0))[eet.notna()].mean()
    L += [f"- Mercados con t tomado de close_time (sin expected_expiration_time): {ref_from_close:.1%}.",
          f"- Diagnóstico anti-fuga: expected_expiration_time con segundos ≠ 0 o minutos no múltiplos de 5 "
          f"(señal de haberse fijado a posteriori): {odd:.2%}.", ""]

    cat = uni.groupby("category").agg(mercados=("ticker", "size"), binarios=("binary", "sum"),
                                      vol_pos=("vol_pos", "sum"), elegibles=("eligible", "sum"),
                                      eventos=("event_ticker", "nunique"))
    sc = obs.groupby("category").agg(muestreados=("ticker", "size"), con_p=("has_p", "sum"),
                                     trade_ventana=("fresh", "sum"), senal=("signal", "sum"),
                                     ejecutable=("exec", "sum"))
    cat = cat.join(sc, how="left").fillna(0).astype(int).sort_values("mercados", ascending=False)
    cat.loc["TOTAL"] = cat.sum()
    L += ["### Por categoría de serie", "", md(cat), ""]

    thr = uni.loc[uni.sampled, "ev_h"].max() if uni.sampled.any() else np.nan
    L += [f"Muestreo: eventos en orden creciente de sha256(event_ticker) hasta alcanzar el presupuesto "
          f"de mercados elegibles; umbral de hash resultante = {thr:.4f} (≈ {thr:.1%} de los eventos). "
          f"Elegibles muestreados: {len(samp)} en {samp.event_ticker.nunique()} eventos.", ""]

    mon = uni.groupby("month").agg(mercados=("ticker", "size"), elegibles=("eligible", "sum"))
    mon = mon.join(obs.groupby(obs.month).agg(muestreados=("ticker", "size"), trade_ventana=("fresh", "sum"),
                                                ejecutable=("exec", "sum")), how="left").fillna(0).astype(int)
    L += ["### Por mes de liquidación", "", md(mon), ""]

    L += ["## Cobertura de trades (muestra elegible)", "",
          f"- Con caché de trades: {int(obs.has_cache.sum())} / {len(obs)}.",
          f"- Con algún trade ≤ t (P_yes definido): {int(obs.has_p.sum())} ({obs.has_p.mean():.1%}).",
          f"- Con trade en (t−1 h, t]: {int(obs.fresh.sum())} ({obs.fresh.mean():.1%}).",
          f"- Con señal (P_yes ≤ 0.10 o ≥ 0.90): {int(obs.signal.sum())}; de ellos con compra taker del lado "
          f"en la ventana (precio ejecutable): {int(obs.exec.sum())}.",
          f"- Edad del último trade (h), cuantiles 25/50/75/90: "
          f"{np.round(obs.p_age.dropna().quantile([.25, .5, .75, .9]).values / 3600, 2).tolist()}", ""]

    # calibración (resultado yes/no únicamente; anulados aparte)
    o = obs[obs.has_p & obs.result.isin(["yes", "no"])].copy()
    o["y"] = (o.result == "yes").astype(float)
    bins = [0, .02, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, .98, 1.0001]
    o["bin"] = pd.cut(o.p_yes, bins, right=False)

    def cal(d):
        g = d.groupby("bin", observed=True).agg(n=("y", "size"), eventos=("event_ticker", "nunique"),
                                                p_media=("p_yes", "mean"), frec_yes=("y", "mean"))
        g["se"] = np.sqrt(g.frec_yes * (1 - g.frec_yes) / g.n)
        g["frec−p"] = g.frec_yes - g.p_media
        return g

    L += ["## Calibración en t (entrenamiento; P_yes = último trade ≤ t)", "",
          "Toda la muestra elegible con P_yes definido (cualquier antigüedad del último trade):", "",
          md(cal(o)), "", "Solo mercados con trade en (t−1 h, t] (precio fresco):", "", md(cal(o[o.fresh])), "",
          "Nota: se = error binomial ingenuo (no agrupa por evento; los mercados de un mismo evento "
          "están correlacionados, así que la incertidumbre real es mayor).", ""]
    open(OUT, "w").write("\n".join(L))
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
