"""H034 G2 (solo entrenamiento, closedTime < 2026-04-12). Protocolo: HYPOTHESES.md ### H034.

    PYTHONPATH=src python3 experiments/h034_g2.py --extract   → data/h034/markets.parquet
    PYTHONPATH=src python3 experiments/h034_g2.py --series    (descarga trades de series)
    PYTHONPATH=src python3 experiments/h034_g2.py --props     (descarga trades de props elegibles)
    PYTHONPATH=src python3 experiments/h034_g2.py             → reports/h034_g2.md

Una sola variante (la pre-registrada). Robustez (costes x2, sin top-5) no son variantes.
"""
import glob, gzip, hashlib, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h034
from pmq.universe import DATA

D = os.path.join(DATA, "h034")
CACHE = os.path.join(DATA, "trades_h034")
os.makedirs(D, exist_ok=True)
EPOCH = pd.Timestamp(0, tz="UTC")
HOLD = h001.HOLDOUT_START
SIZE_CAP_USD = 100.0      # tamaño máximo por entrada (capital < 1000 USD); además ≤ tamaño del trade
BANKROLL = 1000.0


def _ev(d):
    ev = d.get("events")
    if isinstance(ev, list) and ev:
        return str(ev[0].get("id")), ev[0].get("title")
    if isinstance(ev, str):
        m, t = re.search(r"'id': '(\d+)'", ev), re.search(r"'title': '([^']*)'", ev)
        return (m.group(1) if m else None), (t.group(1) if t else None)
    return None, None


def _scan(f):
    out = []
    with gzip.open(f, "rt") as fh:
        for line in fh:
            if "(BO" not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            eid, title = _ev(d)
            if not eid or h034.best_of(title) is None:
                continue
            q = d.get("question") or ""
            out.append(dict(id=int(d["id"]), eid=eid, etitle=title, question=q,
                            smt=d.get("sportsMarketType"), ct_raw=d.get("closedTime"),
                            rule=h034.has_rule(d.get("description")),
                            last=h034.is_last_game_prop(q, d.get("description"), title)))
    return out


def extract():
    fs = sorted(glob.glob(os.path.join(DATA, "gamma", "win_*.jsonl.gz")))
    rows = []
    with Pool(4) as p:
        for o in p.imap_unordered(_scan, fs, chunksize=8):
            rows.extend(o)
    g = pd.DataFrame(rows).drop_duplicates("id")
    g["bo"] = g.etitle.map(h034.best_of)
    g["ct"] = pd.to_datetime(g.ct_raw, utc=True, errors="coerce", format="mixed")
    # series market: moneyline; si falta sportsMarketType, la pregunta lleva "(BOk)" y no "Game/Map N"
    g["is_series"] = (g.smt == "moneyline") | (g.smt.isna() & g.question.str.contains(r"\(BO\d+\)") &
                                                 g.question.map(h034.game_number).isna())
    u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                        columns=["id", "condition_id", "y", "start", "closed_time", "event_id", "fee_schedule"])
    g = g.merge(u, on="id", how="left")
    g.drop(columns=["ct_raw"]).to_parquet(os.path.join(D, "markets.parquet"))
    print("markets", len(g), "events", g.eid.nunique(), flush=True)


def ts(x):
    return int((x - EPOCH) // pd.Timedelta(seconds=1))


def build_events(log):
    g = pd.read_parquet(os.path.join(D, "markets.parquet"))
    log.append(("Mercados con evento '(BOk)' en Gamma", len(g), g.eid.nunique()))
    g = g[(g.bo >= 3) & (g.bo % 2 == 1)]
    log.append(("Eventos Bo3/Bo5/Bo7 (N máximo impar)", len(g), g.eid.nunique()))
    # sin holdout: todo el evento debe haber cerrado antes de HOLD (y con closedTime conocido)
    bad = g.groupby("eid").ct.apply(lambda s: s.isna().any() or (s >= HOLD).any())
    g = g[g.eid.map(bad) == False]  # noqa: E712
    log.append(("…con todos los mercados cerrados antes de 2026-04-12", len(g), g.eid.nunique()))
    props = g[g["last"]]
    log.append(("Props Game/Map N=máx con regla 50-50 de serie decidida", len(props), props.eid.nunique()))
    ser = g[g.is_series].groupby("eid")
    one = ser.size()
    ok = one[one == 1].index
    s = g[g.is_series & g.eid.isin(ok)].set_index("eid")
    props = props[props.eid.isin(ok)]
    log.append(("…con un único mercado de serie en el evento", len(props), props.eid.nunique()))
    props = props[props.condition_id.notna() & props.y.notna() & props.eid.map(s.condition_id).notna()]
    log.append(("…en universo (condition_id, resolución conocida)", len(props), props.eid.nunique()))
    return props, s


def series_window(s):
    return ts(s.start) - 3600, ts(s.ct) + 3600


def fetch_series(s):
    def one(r):
        a, b = series_window(r)
        return h034.fetch_full(r.condition_id, a, b, CACHE)
    with ThreadPoolExecutor(3) as ex:
        return dict(zip(s.index, ex.map(one, [r for _, r in s.iterrows()])))


def fetch_props(props):
    def one(r):
        return h034.fetch_full(r.condition_id, ts(r.start) - 3600, int(r.t_d) + h034.WINDOW_S, CACHE)
    with ThreadPoolExecutor(3) as ex:
        return list(ex.map(one, [r for _, r in props.iterrows()]))


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def main():
    log = []
    props, s = build_events(log)
    if "--series" in sys.argv:
        print("series", len(s.loc[props.eid.unique()]), flush=True)
        r = fetch_series(s.loc[props.eid.unique()])
        print("fallos", sum(v is None for v in r.values()), flush=True)
        return
    st = fetch_series(s.loc[props.eid.unique()])
    fail_s = sum(v is None for v in st.values())
    td = {e: (h034.decided_time(v) if v is not None else None) for e, v in st.items()}
    props = props.assign(t_d=props.eid.map(td))
    props = props[props.t_d.notna()].copy()
    log.append(("…con t_d (serie tocó ≥0.99) [fallos de descarga serie: %d]" % fail_s, len(props), props.eid.nunique()))
    if "--props" in sys.argv:
        print("props", len(props), flush=True)
        r = fetch_props(props)
        print("fallos", sum(v is None for v in r), flush=True)
        return
    pt = fetch_props(props)
    props["fail"] = [x is None for x in pt]
    props["trades"] = pt
    props = props[~props.fail].copy()
    log.append(("…trades del prop descargados", len(props), props.eid.nunique()))
    props["n_trades"] = [len(x) for x in props.trades]
    props["ok"] = [h034.prop_ok(x, int(t)) for x, t in zip(props.trades, props.t_d)]
    props["void"] = props.y == 0.5
    elig = props[props.ok].copy()
    log.append(("…sin trade del prop a ≥0.99/≤0.01 hasta t_d", len(elig), elig.eid.nunique()))
    base_void = (elig.void.mean(), props[~props.ok].void.mean())
    elig["rate"] = [h001.fee_rate(x) for x in elig.fee_schedule]
    rows = []
    for _, r in elig.iterrows():
        for e in h034.entries(r.trades, int(r.t_d), r.rate):
            rows.append(dict(id=r.id, eid=r.eid, etitle=r.etitle, question=r.question, y=r.y, rate=r.rate,
                             t_d=int(r.t_d), ct=r.ct, **e))
    b = pd.DataFrame(rows)
    log.append(("Entradas (≤1 por token) en (t_d+15m, t_d+6h]", len(b), b.eid.nunique() if len(b) else 0))
    rep = report_lines(log, props, elig, b, base_void)
    open(os.path.join(ROOT, "reports", "h034_g2.md"), "w").write("\n".join(rep) + "\n")
    b.to_parquet(os.path.join(D, "entries.parquet"))
    print("\n".join(rep))


def ci(df, col):
    return h001.cluster_bootstrap(df, col=col, cluster="eid", n=4000, seed=0)


def report_lines(log, props, elig, b, base_void):
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    L = ["# H034 G2 — props esports 'Game/Map N' anulados 50-50 (entrenamiento)", "",
         f"Commit base: {commit} · markets.parquet sha256[:16]={sha(os.path.join(D, 'markets.parquet'))} · "
         f"comando: `PYTHONPATH=src python3 experiments/h034_g2.py` · variantes: 1 (pre-registrada)", "",
         "## Filtros", "", "| paso | mercados | eventos (series) |", "|---|---:|---:|"]
    L += [f"| {a} | {m} | {e} |" for a, m, e in log]
    L += ["", f"Tasa de anulación (y=0.5) entre props elegibles: {base_void[0]:.3f}; "
          f"entre props descartados por trade extremo previo: {base_void[1]:.3f}.", ""]
    if not len(b):
        return L + ["Sin entradas."]
    b["pay"] = [h034.payoff(y, k) for y, k in zip(b.y, b.outcome)]
    b["void"] = b.y == 0.5
    b["pnl"] = [h034.pnl(p, r, pa) for p, r, pa in zip(b.price, b.rate, b.pay)]
    b["pnl2"] = [h034.pnl(p, r, pa, 2.0, 0.01) for p, r, pa in zip(b.price, b.rate, b.pay)]
    b["c1"] = [h034.cost(p, r) for p, r in zip(b.price, b.rate)]
    b["c2"] = [h034.cost(p, r, 2.0, 0.01) for p, r in zip(b.price, b.rate)]
    b["usd_trade"] = b["size"] * b.price
    b["sh"] = np.minimum(b["size"], SIZE_CAP_USD / b.c1)
    b["cap"] = b.sh * b.c1
    b["pnl_usd"] = b.sh * b.pnl
    b["pnl2_usd"] = b.sh * b.pnl2
    b["cap2"] = b.sh * b.c2
    ent = pd.to_datetime(b.ts, unit="s", utc=True)
    b["days"] = ((b.ct - ent).dt.total_seconds() / 86400).clip(lower=1 / 24)
    b["month"] = ent.dt.strftime("%Y-%m")
    nv = b.void.mean()
    lo, hi = ci(b, "pnl")
    lo2, hi2 = ci(b, "pnl2")
    b["ret"] = b.pnl_usd / b.cap
    usd = b.pnl_usd.sum() / b.cap.sum()
    usd2 = b.pnl2_usd.sum() / b.cap2.sum()
    # IC del retorno por USD: bootstrap de razón por clusters
    g = b.groupby("eid")[["pnl_usd", "cap", "pnl2_usd", "cap2"]].sum()
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(g), size=(4000, len(g)))
    r1 = g.pnl_usd.values[idx].sum(1) / g.cap.values[idx].sum(1)
    r2 = g.pnl2_usd.values[idx].sum(1) / g.cap2.values[idx].sum(1)
    top = g.pnl_usd.sort_values(ascending=False).index[:5]
    bt = b[~b.eid.isin(top)]
    lo5, hi5 = ci(bt, "pnl")
    span = (b.ts.max() - b.ts.min()) / 86400
    L += ["## Resultados (precio = trade taker BUY real; tamaño ≤ tamaño del trade y ≤ 100 USD)", "",
          f"- Entradas: {len(b)} en {b.id.nunique()} props, {b.eid.nunique()} series (clusters); "
          f"meses: {b.month.min()}…{b.month.max()}",
          f"- **Tasa de anulación observada en las entradas: {nv:.3f}** (criterio ≥ 0.90)",
          f"- Precio de entrada: mediana {b.price.median():.3f}, media {b.price.mean():.3f}; "
          f"comisión media {np.mean(b.rate):.3f}·p(1−p)",
          f"- PnL/acción (equiponderado): {b.pnl.mean():+.4f}  IC95% cluster [{lo:+.4f}, {hi:+.4f}]",
          f"- PnL/acción costes x2 (comisión x2 + 0.01 slippage): {b.pnl2.mean():+.4f}  IC95% [{lo2:+.4f}, {hi2:+.4f}]",
          f"- Retorno por USD (Σpnl/Σcoste): {usd:+.4f}  IC95% [{np.percentile(r1, 2.5):+.4f}, {np.percentile(r1, 97.5):+.4f}]; "
          f"costes x2: {usd2:+.4f}  IC95% [{np.percentile(r2, 2.5):+.4f}, {np.percentile(r2, 97.5):+.4f}]",
          f"- Sin las 5 mejores series: PnL/acción {bt.pnl.mean():+.4f}  IC95% [{lo5:+.4f}, {hi5:+.4f}]; "
          f"por USD {bt.pnl_usd.sum() / bt.cap.sum():+.4f}",
          f"- Tamaño del trade histórico: mediana {b['size'].median():.1f} acciones = {b.usd_trade.median():.2f} USD; "
          f"p90 {b.usd_trade.quantile(.9):.2f} USD",
          f"- Capacidad: Σ coste ejecutable {b.cap.sum():.0f} USD en {span:.0f} días "
          f"(≈ {b.cap.sum() / max(span, 1) * 30:.0f} USD/mes); PnL total {b.pnl_usd.sum():+.2f} USD "
          f"(≈ {b.pnl_usd.sum() / max(span, 1) * 30:+.2f} USD/mes)",
          f"- Días bloqueados: mediana {b.days.median():.2f}; retorno de cartera Σpnl/Σ(capital·días)·365 = "
          f"{h034.portfolio_return(b.pnl_usd, b.cap, b.days):+.2f}",
          f"- Con banca fija de {BANKROLL:.0f} USD durante el periodo: "
          f"{b.pnl_usd.sum() / BANKROLL / max(span, 1) * 365:+.3f} anual", "",
          "## Veredicto frente a la predicción pre-registrada", "",
          f"- PnL > 0 con IC95% > 0: {'SÍ' if lo > 0 and b.pnl.mean() > 0 else 'NO'}",
          f"- ≥ 150 series: {'SÍ' if b.eid.nunique() >= 150 else 'NO'} ({b.eid.nunique()})",
          f"- Tasa de anulación en operaciones ≥ 0.90: {'SÍ' if nv >= 0.9 else 'NO'} ({nv:.3f}) — "
          "si falla, la identificación 'partida N no jugada' con t_d no es fiable: el mercado de serie "
          "llega a ≥0.99 al terminar la partida N (que sí se jugó) y los tokens baratos comprados son "
          "los perdedores de esa partida (selección adversa).", "",
          "### Por resolución del prop", "", "| resolución | n | PnL/acción medio | precio medio |", "|---|---:|---:|---:|"]
    for k, x in b.groupby(np.where(b.void, "anulado (0.5)", np.where(b.pay == 1, "token gana", "token pierde"))):
        L.append(f"| {k} | {len(x)} | {x.pnl.mean():+.4f} | {x.price.mean():.3f} |")
    L += ["", "### Por juego", "", "| juego | n | series | anul. | PnL/acción |", "|---|---:|---:|---:|---:|"]
    for k, x in b.groupby(b.etitle.str.split(":").str[0]):
        L.append(f"| {k} | {len(x)} | {x.eid.nunique()} | {x.void.mean():.2f} | {x.pnl.mean():+.4f} |")
    L += ["", "### Por mes", "", "| mes | n | series | anul. | PnL/acción | coste USD |", "|---|---:|---:|---:|---:|---:|"]
    for k, x in b.groupby("month"):
        L.append(f"| {k} | {len(x)} | {x.eid.nunique()} | {x.void.mean():.2f} | {x.pnl.mean():+.4f} | {x.cap.sum():.0f} |")
    return L


if __name__ == "__main__":
    if "--extract" in sys.argv:
        extract()
    else:
        main()
