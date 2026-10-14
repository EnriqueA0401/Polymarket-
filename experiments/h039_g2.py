"""H039 G2 (histórico, solo entrenamiento): arbitraje Kalshi ↔ Polymarket en partidos emparejados por H023.
Por partido y minuto antes del inicio con compras taker en ambas plataformas: coste = peor compra Kalshi de
la exposición "gana e" + peor compra PM del token del otro equipo + comisiones. Oportunidad si < 0.99.
Incluye la auditoría de reglas de resolución (aplazamiento, cancelación, empate) y casos históricos.
python experiments/h039_g2.py [--fetch-only] → data/h039/pairs.parquet, reports/h039_g2.md"""
import argparse, collections, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h023 as H, h039 as A
from pmq.universe import DATA

ap = argparse.ArgumentParser(); ap.add_argument("--fetch-only", action="store_true")
ap.add_argument("--limit", type=int, default=0, help="solo depuración: primeros N partidos")
args = ap.parse_args()
os.makedirs(A.CACHE, exist_ok=True)

g = pd.read_parquet(os.path.join(H.CACHE, "matches.parquet"))          # 3,962 partidos de entrenamiento
assert (g.closed_time < H.HOLDOUT_START).all()
kmk = {lg: H.k_markets(s) for lg, (s, _) in H.LEAGUES.items()}
kev = {e["event_ticker"]: e for lg in kmk for e in H.k_events(kmk[lg], lg)}
kby = {m["ticker"]: m for lg in kmk for m in kmk[lg]}
g["k_ticker1"] = [kev[ev]["mk"][t1]["ticker"] for ev, t1 in zip(g.k_event, g.team1)]
assert all(kev[ev]["mk"][t0]["ticker"] == k0 for ev, t0, k0 in zip(g.k_event, g.team0, g.k_ticker0))
g["a"] = g.gs - A.LOOKBACK
if args.limit:
    g = g.head(args.limit)

# ---------------------------------------------------------------------------------------------
# Descargas (cacheadas) y pares por partido
# ---------------------------------------------------------------------------------------------
def game(r, fetch_only=False):
    """Descarga (caché) y calcula los pares de un partido; no guarda los trades en memoria."""
    try:
        k0, k1 = A.k_trades(r.k_ticker0, r.a, r.gs), A.k_trades(r.k_ticker1, r.a, r.gs)
    except RuntimeError:
        k0 = k1 = None
    pt = A.pm_trades(r.condition_id, r.a, r.gs)
    if fetch_only:
        return None, None
    kb = pd.concat([A.k_buys(k0, 0), A.k_buys(k1, 1)], ignore_index=True)
    pb = A.pm_buys(pt)
    pr = A.pairs(kb, pb, r.gs, r.rate)
    for C in (1, 10):                                        # sensibilidad al redondeo de Kalshi
        pr[f"cost_c{C}"] = [A.pair_cost(a, b, r.rate, C) for a, b in zip(pr.pk, pr.pp)]
    pr["cost_x2"] = pr.pk + pr.pp + 2 * (pr.cost - pr.pk - pr.pp)     # comisiones ×2
    pr["pay"] = [A.pair_payoff(e, r.y, r.k_y0) for e in pr.e]          # pago realizado (debe ser 1)
    pr["id"] = r.id
    cv = {"id": r.id, "k_fail": k0 is None or k1 is None, "pm_fail": pt is None,
          "k_buys": int((kb.t < r.gs).sum()) if len(kb) else 0, "pm_buys": int((pb.t < r.gs).sum()) if len(pb) else 0,
          "k0_n": len(k0 or []), "k1_n": len(k1 or []), "pm_n": len(pt or [])}
    return pr, cv

n = len(g)
done = [0]
def run(r):
    out = game(r, args.fetch_only)
    done[0] += 1
    if done[0] % 200 == 0:
        print("partidos", done[0], "/", n, flush=True)
    return out

with ThreadPoolExecutor(4) as ex:
    res = list(ex.map(run, list(g.itertuples())))
if args.fetch_only:
    print("descarga terminada", flush=True)
    sys.exit(0)
rows = [x for x, _ in res]
cov = [c for _, c in res]
P = pd.concat(rows, ignore_index=True)
cov = pd.DataFrame(cov)
P = P.merge(g[["id", "league", "season", "gs", "rate"]], on="id")
P["h_before"] = (P.gs - (P.minute * 60 + 60)) / 3600
P.to_parquet(os.path.join(A.CACHE, "pairs.parquet"))
cov.to_parquet(os.path.join(A.CACHE, "coverage.parquet"))

# ---------------------------------------------------------------------------------------------
# Análisis
# ---------------------------------------------------------------------------------------------
P["opp"] = P.cost < A.THRESH
O = P[P.opp].copy()
O["minsz"] = np.minimum(O.k_size, O.pm_size)
O["minsz_w"] = np.minimum(O.k_size_w, O.pm_size_w)
first = O.sort_values("minute").groupby("id").head(1)       # primera oportunidad por partido (sin lookahead)
best = O.sort_values("profit").groupby("id").tail(1)
q = lambda s, ps=(0.05, 0.25, 0.5, 0.75, 0.95): " / ".join(f"{s.quantile(p):.4f}" for p in ps) if len(s) else "—"

def ngames(mask):
    return P[mask].id.nunique()

sens = pd.DataFrame([
    {"variante de coste": "principal (C=100, comisiones ×1)", "minutos_opp": int(P.opp.sum()), "partidos_opp": ngames(P.opp)},
    {"variante de coste": "redondeo Kalshi C=10", "minutos_opp": int((P.cost_c10 < A.THRESH).sum()), "partidos_opp": ngames(P.cost_c10 < A.THRESH)},
    {"variante de coste": "redondeo Kalshi C=1", "minutos_opp": int((P.cost_c1 < A.THRESH).sum()), "partidos_opp": ngames(P.cost_c1 < A.THRESH)},
    {"variante de coste": "comisiones ×2 (C=100)", "minutos_opp": int((P.cost_x2 < A.THRESH).sum()), "partidos_opp": ngames(P.cost_x2 < A.THRESH)},
    {"variante de coste": "principal y |Δt| peor compra ≤ 5 s", "minutos_opp": int((P.opp & (P.dt <= 5)).sum()), "partidos_opp": ngames(P.opp & (P.dt <= 5))},
    {"variante de coste": "principal y min(tamaño) ≥ 100", "minutos_opp": int((P.opp & (np.minimum(P.k_size, P.pm_size) >= 100)).sum()),
     "partidos_opp": ngames(P.opp & (np.minimum(P.k_size, P.pm_size) >= 100))},
    {"variante de coste": "principal y beneficio ≥ 0.02", "minutos_opp": int((P.cost < 0.98).sum()), "partidos_opp": ngames(P.cost < 0.98)},
])
by = P.groupby(["league", "season"]).agg(partidos_con_par=("id", "nunique"), minutos_par=("id", "size"))
by["partidos_opp"] = O.groupby(["league", "season"]).id.nunique()
by["minutos_opp"] = O.groupby(["league", "season"]).size()
by["benef_medio_1a_opp"] = first.groupby(["league", "season"]).profit.mean()
by = by.fillna(0)
bins = [-1, 0.95, 0.97, 0.98, 0.99, 1.0, 1.01, 1.02, 1.05, 10]
hist = pd.cut(P.cost, bins).value_counts().sort_index()
hb = pd.cut(O.h_before, [0, 0.25, 1, 3, 6, 24, 72, 400]).value_counts().sort_index()
rate_hist = g.rate.value_counts().to_dict()

# ---------------------------------------------------------------------------------------------
# Auditoría de reglas
# ---------------------------------------------------------------------------------------------
pm = pd.read_parquet(os.path.join(H.CACHE, "pm_moneyline.parquet"))
u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                    columns=["id", "condition_id", "y", "clean", "closed_time", "event_id", "fee_schedule", "uma_status"])
pmu = pm.merge(u, on="id", how="inner")
pmu = pmu[pmu.closed_time < H.HOLDOUT_START]                           # holdout intacto
desc = dict(zip(pm.id, pm.description))

def pm_flags(d):
    d = (d or "").lower()
    return ("remain open until the game has been completed" in d,
            "canceled entirely" in d and "50-50" in d,
            "tie" in re.sub(r"[^a-z ]", " ", d).split())

def k_class(s):
    """Plantilla de Kalshi (rules_secondary): ventana de aplazamiento y regla de cancelación."""
    s = (s or "").lower()
    if not s:
        return "vacío en API histórica"
    w = ("2 años" if "two years" in s else "2 semanas" if "two weeks" in s else
         "48 h / 2 días" if ("two days" in s or "48 hours" in s) else "otra")
    c = "50/50" if "50/50" in s else "precio justo" if "fair" in s else "otra"
    return f"aplazado ≤ {w}; cancelado → {c}"

aud, kcls = [], []
for r in g.itertuples():
    pf = pm_flags(desc.get(r.id))
    aud.append({"league": r.league, "PM: aplazado→abierto hasta jugarse": pf[0], "PM: cancelado→50-50": pf[1],
                "PM: empate mencionado": pf[2]})
    kcls.append({"league": r.league, "season": r.season, "plantilla Kalshi": k_class(kby[r.k_ticker0].get("rules_secondary"))})
kcls = pd.DataFrame(kcls).groupby(["league", "season", "plantilla Kalshi"]).size().rename("partidos").reset_index()
aud = pd.DataFrame(aud).groupby("league").mean().round(3)

# casos históricos de Kalshi no binarios (escalar) con fecha < holdout
kz = []
for e in kev.values():
    if e["date"] >= H.HOLDOUT_START.date():
        continue
    res = {t: v["result"] for t, v in e["mk"].items()}
    if all(x in ("yes", "no") for x in res.values()):
        continue
    teams = list(e["mk"])
    cand = pmu[(pmu.league == e["league"])]
    hit = []
    for c in cand.itertuples():
        nm = H.pm_full_names(c.description, [c.o0, c.o1], c.league)
        if nm and set(nm) == set(teams) and pd.notna(c.game_start) and \
                -3 <= (c.game_start.tz_convert("America/New_York").date() - e["date"]).days <= 150:
            hit.append((c.id, nm[0], c.y, c.clean, c.closed_time, c.game_start))
    sv = {t: v["settle"] for t, v in e["mk"].items()}
    kz.append({"k_event": e["event_ticker"], "resultados_K": res, "liquidación_K": sv,
               "PM (id, team0, y, clean, closed, start)": hit[:2] if hit else "sin mercado PM en entrenamiento"})
kz = pd.DataFrame(kz)

# rehacer el emparejamiento de H023 para el conjunto completo 'ok' (incluye discrepancias)
pmt = pmu[pmu.game_start >= pd.Timestamp("2025-04-13", tz="UTC")]
mm = H.match(pmt, list(kev.values())).merge(pmt[["id", "y", "clean", "closed_time", "game_start", "question"]], on="id")
ok = mm[mm.status == "ok"].copy()
ok["k_settle0"] = [float(kev[ev]["mk"][t0]["settle"]) if kev[ev]["mk"][t0]["settle"] is not None else np.nan
                   for ev, t0 in zip(ok.k_event, ok.team0)]
ok["pay_e0"] = [A.pair_payoff(0, y, k) for y, k in zip(ok.y, ok.k_settle0)]
ok["pay_e1"] = [A.pair_payoff(1, y, k) for y, k in zip(ok.y, ok.k_settle0)]
ok["worst"] = ok[["pay_e0", "pay_e1"]].min(axis=1)
bad = ok[(ok.worst - 1).abs() > 1e-9]
late = pmt[(pmt.closed_time - pmt.game_start) > pd.Timedelta("2D")]
pm_half = pmt[pmt.y == 0.5]

# ---------------------------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------------------------
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
n_opp = O.id.nunique()
mean_first = first.profit.mean() if len(first) else np.nan
mean_all = O.profit.mean() if len(O) else np.nan
pred_n = n_opp >= 150
pred_p = (mean_first >= 0.01) if len(first) else False
L = ["# H039 G2 — arbitraje Kalshi ↔ Polymarket (histórico, entrenamiento)", "",
     f"- commit {commit}; código: src/pmq/h039.py, experiments/h039_g2.py; datos: data/h039 (pairs.parquet, coverage.parquet), "
     "data/h023 (matches, mercados y trades Kalshi del equipo 0), Data API PM (data/h039/pmtrades), Kalshi API (data/h039/ktrades)",
     f"- partidos: {n} (H023, entrenamiento, resoluciones coincidentes; holdout PM closedTime ≥ 2026-04-12 sin tocar)",
     f"- ventana: [inicio − 14 días, inicio); minutos de reloj (UTC) con compras taker en ambas plataformas; ambos mercados de "
     "Kalshi (YES del equipo e o NO del rival = exposición 'gana e'); lado PM = token del otro equipo (solo BUY taker)",
     f"- precio de cada lado = peor (máxima) compra del minuto; Kalshi taker ceil_céntimo(0.07·C·P·(1−P)) con C={A.C_REF} "
     f"(fee_multiplier de MLB es 0.5 hoy; se usa 1, pesimista); PM rate·p·(1−p), rate del mercado o 0.07: {rate_hist}",
     f"- descargas fallidas: Kalshi {int(cov.k_fail.sum())}, PM {int(cov.pm_fail.sum())}; partidos sin compras Kalshi pre-partido "
     f"{int((cov.k_buys == 0).sum())}, sin compras PM {int((cov.pm_buys == 0).sum())}",
     "", "## Resultado principal", "",
     f"- pares (partido, minuto, dirección) con compras en ambas: {len(P):,} en {P.id.nunique():,} partidos",
     f"- coste por par (cuantiles 5/25/50/75/95 %): {q(P.cost)}",
     f"- **oportunidades (coste < 0.99): {len(O):,} pares-minuto en {n_opp:,} partidos**",
     f"- beneficio por par en oportunidades (todas): media {mean_all:.4f}; cuantiles 5/25/50/75/95 %: {q(O.profit)}",
     f"- **beneficio de la primera oportunidad de cada partido: media {mean_first:.4f}**; mediana "
     f"{first.profit.median() if len(first) else np.nan:.4f}; mejor oportunidad por partido: media "
     f"{best.profit.mean() if len(best) else np.nan:.4f}",
     f"- pago realizado de todos los pares (partidos con resolución coincidente): min {P.pay.min():.3f}, max {P.pay.max():.3f} (debe ser 1)",
     "", "### Distribución del coste por par", "", hist.rename("pares").to_frame().to_markdown(), "",
     "### Por liga y temporada", "", by.to_markdown(floatfmt=".4f"), "",
     "### Sensibilidad (no son variantes; misma regla, otros supuestos de coste/ejecución)", "", sens.to_markdown(index=False), "",
     "## Ejecutabilidad (oportunidades)", "",
     f"- tamaño negociado en el minuto, min(Kalshi contratos, PM acciones), cuantiles 5/25/50/75/95 %: {q(O.minsz)}",
     f"- tamaño AL peor precio, min de ambos lados: {q(O.minsz_w)}",
     f"- fracción con min(tamaño) ≥ 10: {(O.minsz >= 10).mean():.3f}; ≥ 100: {(O.minsz >= 100).mean():.3f}; "
     f"≥ 1000: {(O.minsz >= 1000).mean():.3f}" if len(O) else "- sin oportunidades",
     f"- |Δt| entre las dos peores compras (s), cuantiles: {q(O.dt)}; fracción ≤ 5 s: {(O.dt <= 5).mean():.3f}" if len(O) else "",
     f"- dirección Kalshi e=0/e=1: {O.e.value_counts().to_dict()}",
     "", "### Horas antes del inicio (oportunidades)", "", hb.rename("pares").to_frame().to_markdown(), "",
     "## Auditoría de reglas de resolución", "",
     "Fracción de partidos usados cuyo texto contiene cada cláusula (PM: descripción de Gamma; Kalshi: rules_secondary "
     "del mercado del equipo 0):", "", aud.to_markdown(), "",
     "Plantillas de Kalshi (rules_secondary del mercado del equipo 0) en los partidos usados:", "",
     kcls.to_markdown(index=False), "",
     "Reglas vigentes (contract terms PDF BASKETBALL/BASEBALL/FOOTBALLGAMEWIN y rules_secondary de mercados abiertos, "
     "consultados 2026-10-14): aplazado y no iniciado en 48 h → 'last fair price' fijado por el Exchange; cancelado → "
     "precio justo; forfeit antes de empezar → precio justo; empate (sin strike 'Tie') → 0.50/0.50. PM: aplazado → abierto "
     "hasta que se juegue; cancelado sin recuperación → 50-50; NFL empate → 50-50 (descripciones nuevas).", "",
     "- **Aplazamiento**: PM mantiene el mercado abierto hasta que el partido se juegue (sin límite); Kalshi espera ≤ 48 h "
     "/ 2 días y después liquida a 'precio justo' (fair price, escalar). Un aplazamiento > 2 días rompe el par: la pata de Kalshi "
     "paga ≈ el precio justo y la de PM paga 0 o 1 según el partido de recuperación → pago total ∈ [f, 1 + f], no 1.",
     "- **Cancelación**: PM 50-50; Kalshi 'precio justo' (no necesariamente 0.50) → pago ≠ 1 salvo que precio justo = 0.50.",
     "- **Empate (NFL)**: Kalshi 0.50 a cada equipo; PM: las descripciones nuevas dicen 50-50, las antiguas no lo mencionan.",
     "- **Fuente y momento**: Kalshi liquida con la liga/ESPN; PM vía oráculo UMA (propuesta + ventana de disputa) → riesgo de "
     "disputa sólo en una pata.", "",
     f"### Partidos emparejados 'ok' en entrenamiento cuyo par NO paga 1 (peor dirección), de {len(ok):,}", "",
     f"- casos: {len(bad)} ({len(bad) / max(len(ok), 1):.2%}); pago medio en la peor dirección: "
     f"{bad.worst.mean() if len(bad) else np.nan:.3f}; pérdida esperada por par ≈ {(1 - ok.worst).clip(lower=0).mean():.4f} USD",
     "", bad[["id", "question", "game_start", "k_event", "y", "k_settle0", "pay_e0", "pay_e1"]].to_markdown(index=False) if len(bad) else "(ninguno)",
     "", "### Eventos de Kalshi liquidados a valor escalar (fecha < holdout)", "",
     kz.to_markdown(index=False) if len(kz) else "(ninguno)", "",
     f"- mercados PM moneyline de entrenamiento cerrados > 2 días después de gameStartTime: {len(late)} "
     f"(posibles aplazamientos largos; ids muestra {late.id.head(10).tolist()}); PM resueltos 50-50: {len(pm_half)} "
     f"(ids {pm_half.id.head(10).tolist()})", "",
     "## Veredicto frente a la predicción G0", "",
     f"- ≥ 150 partidos con oportunidad: {'sí' if pred_n else 'NO'} ({n_opp})",
     f"- beneficio medio ≥ 1 c por par tras comisiones (primera oportunidad por partido): {'sí' if pred_p else 'NO'} ({mean_first:.4f})",
     "- reglas de resolución idénticas: **NO** (aplazamiento > 48 h y cancelación difieren; ver auditoría)",
     "- Advertencias: 'mismo minuto' no es simultáneo; el peor precio del minuto no garantiza que el otro lado siguiera "
     "disponible; los trades taker no muestran la profundidad del libro (sin historial de libro) → el registro forward con "
     "libros reales (src/pmq/h039live.py) es la prueba ejecutable."]
open(os.path.join(ROOT, "reports", "h039_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L[:20]))
