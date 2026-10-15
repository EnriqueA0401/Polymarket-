"""H038 G2 — PnL en entrenamiento de la señal pre-registrada (1 variante): P_yes ≤ 0.10 → NO,
P_yes ≥ 0.90 → YES en t = cierre programado − 24 h, al PEOR precio de compra taker del lado en
(t−1 h, t], comisión taker vigente de la serie (C = 100 contratos por orden), hasta liquidación.

Requiere data/h038/obs_train.parquet (experiments/h038_g1.py).
  PYTHONPATH=src python3 experiments/h038_g2.py
"""
import os, subprocess
import numpy as np
import pandas as pd

from pmq import h038
from pmq.h001 import cluster_bootstrap

OUT = os.path.join(os.path.dirname(__file__), "..", "reports", "h038_g2.md")


def summ(tr, label):
    if not len(tr):
        return dict(caso=label, n=0)
    lo, hi = cluster_bootstrap(tr, "pnl", "event_ticker", n=4000, seed=0)
    return dict(caso=label, n=len(tr), eventos=tr.event_ticker.nunique(), pnl_contrato=tr.pnl.mean(),
                ic95_lo=lo, ic95_hi=hi, acierto=(tr.pnl > 0).mean(), precio_medio=tr.exec_price.mean(),
                ret_cartera_anual=tr.pnl.sum() / (tr.capital * tr.days).sum() * 365,
                dias_medios=tr.days.mean())


def drop_top(tr, k=5):
    top = tr.groupby("event_ticker").pnl.sum().nlargest(k).index
    return tr[~tr.event_ticker.isin(top)]


def md(rows):
    df = pd.DataFrame(rows).set_index("caso")
    for c in df.columns:
        if df[c].dtype.kind == "f":
            df[c] = df[c].round(4)
    return df.to_markdown()


def main():
    obs = pd.read_parquet(os.path.join(h038.CACHE, "obs_train.parquet"))
    assert (pd.to_datetime(obs.settlement_ts.fillna(obs.close_time), utc=True, format="mixed")
            < h038.HOLDOUT_START).all()
    sc = obs[(obs.result == "scalar") & obs.side.notna() & obs.exec_price.notna()].ticker.tolist()
    vals = h038.scalar_values(sc) if sc else {}
    obs["scalar_value"] = obs.ticker.map(vals).astype(float)
    base = h038.add_pnl(obs)
    x2 = h038.add_pnl(obs, fee_mult=2.0, slip2=True)
    c10 = h038.add_pnl(obs, c=10)
    fl1 = h038.add_pnl(obs, mult_floor=1.0)
    base.to_parquet(os.path.join(h038.CACHE, "trades_train.parquet"))

    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        commit = "?"
    L = ["# H038 G2 — Favorito-longshot en Kalshi con precios ejecutables (entrenamiento)", "",
         f"Commit base `{commit}` · generado {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC · "
         "variantes: 1 (pre-registrada). Unidades: USD por contrato (pago 1 USD).", "",
         "## Definiciones", "",
         "- Operación = mercado muestreado con P_yes (último trade ≤ t) ≤ 0.10 (compra NO) o ≥ 0.90 "
         "(compra YES) y al menos una compra taker de ese lado en (t−1 h, t]; precio = la PEOR de esas "
         "compras (no VWAP). Block trades excluidos.",
         "- Comisión: ceil_céntimo(0.07·m·C·P·(1−P)) por orden, C = 100, m = multiplicador vigente de la "
         "serie (/series). Anulados: se devuelve el precio, se pierde la comisión.",
         "- Costes ×2: comisión ×2 y precio empeorado en max(0.01, precio ejecutable − último trade "
         "del lado) (dobla el deslizamiento observado, mínimo un tick).",
         "- Rentabilidad de cartera anualizada = Σpnl / Σ(capital·días) · 365, capital = precio + "
         "comisión por contrato, días = (liquidación − t). No incluye capital ocioso (cota SUPERIOR).",
         "- IC95%: bootstrap por clusters = event_ticker (4000 réplicas).", ""]

    rows = [summ(base, "base"), summ(x2, "costes ×2"), summ(drop_top(base), "sin top-5 eventos"),
            summ(drop_top(x2), "costes ×2 sin top-5"), summ(c10, "C = 10 contratos (redondeo comisión)"),
            summ(fl1, "multiplicador de comisión ≥ 1")]
    for s in ("yes", "no"):
        rows.append(summ(base[base.side == s], f"lado {s.upper()}"))
        rows.append(summ(x2[x2.side == s], f"lado {s.upper()} costes ×2"))
    L += ["## Resultado", "", md(rows), ""]

    cat = [summ(base[base.category == c], c) for c in base.category.value_counts().index]
    L += ["## Por categoría (descriptivo, sin selección)", "", md(cat), ""]

    base["pbin"] = pd.cut(base.exec_price, [0.90, 0.93, 0.96, 0.98, 1.0001], right=False)
    pb = [summ(g, f"precio {k}") for k, g in base.groupby("pbin", observed=True)]
    L += ["## Por precio ejecutable (descriptivo)", "", md(pb), ""]

    per_ev = base.groupby("event_ticker").size()
    L += ["## Costes y capacidad", "",
          f"- Comisión media por contrato: {(base.capital - base.exec_price).mean():.4f} USD; "
          f"deslizamiento medio peor-compra − último trade del lado: {(base.exec_price - base.ref_price).mean():.4f}.",
          f"- Volumen taker del lado en la ventana (contratos), mediana/p25: "
          f"{base.vol_side.median():.0f}/{base.vol_side.quantile(.25):.0f}; operaciones con < 100 contratos "
          f"de volumen en la ventana: {(base.vol_side < 100).mean():.1%} (el tamaño C = 100 no está "
          "garantizado al precio peor observado).",
          f"- Mercados por evento: media {per_ev.mean():.2f}, máx {per_ev.max()} (correlación intra-evento "
          "tratada con el bootstrap por clusters).",
          f"- Resultados: {base.result.value_counts().to_dict()} (escalares liquidados a "
          f"settlement_value_dollars; sin valor → pago 0); mercados con multiplicador ≠ 1: "
          f"{(base.fee_mult.fillna(1) != 1).sum()}.", ""]

    b = rows[0]; c2 = rows[1]
    met = (b.get("ic95_lo", -1) > 0) and (c2.get("pnl_contrato", -1) > 0)
    L += ["## Predicción G0", "",
          "Predicción: PnL > 0 con IC95% cluster > 0 y costes ×2 > 0.", "",
          f"**{'CUMPLIDA' if met else 'NO CUMPLIDA'}** en entrenamiento: PnL/contrato base "
          f"{b.get('pnl_contrato', float('nan')):.4f} [{b.get('ic95_lo', float('nan')):.4f}, "
          f"{b.get('ic95_hi', float('nan')):.4f}], costes ×2 {c2.get('pnl_contrato', float('nan')):.4f}.", ""]
    open(OUT, "w").write("\n".join(L))
    print("\n".join(L[-6:]))


if __name__ == "__main__":
    main()
