"""H014 G1 (solo entrenamiento, closedTime < 2026-04-12): universo, estaciones, pronósticos, sanidad.

    PYTHONPATH=src python3 experiments/h014_g1.py            # todo → reports/h014_g1.md
    PYTHONPATH=src python3 experiments/h014_g1.py --fetch    # solo descarga (reintenta 429)

Salidas en data/h014/: markets.parquet (mercados parseados), om/*.json (Open-Meteo Previous Runs,
horario temperature_2m_previous_day1..3 en UTC), geo.json (geocodificación), forecasts.parquet
(máximo pronosticado por evento con solo información publicada en t).
"""
import glob, gzip, hashlib, json, math, os, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd, requests
from pmq import h001, h014
from pmq.universe import DATA

D = os.path.join(DATA, "h014")
OM = os.path.join(D, "om")
os.makedirs(OM, exist_ok=True)


def scan_gamma():
    """Descripción y endDate crudos de Gamma para los mercados de temperatura máxima."""
    path = os.path.join(D, "gamma_meta.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    rows = []
    for f in sorted(glob.glob(os.path.join(DATA, "gamma", "win_2025-*.jsonl.gz")) +
                    glob.glob(os.path.join(DATA, "gamma", "win_2026-*.jsonl.gz"))):
        for line in gzip.open(f, "rt"):
            if "highest temperature" not in line:
                continue
            m = json.loads(line)
            if "highest temperature" not in (m.get("question") or "").lower():
                continue
            ev = (m.get("events") or [{}])[0]
            rows.append(dict(id=int(m["id"]), description=m.get("description"), resolution_source=m.get("resolutionSource"),
                             event_start=m.get("eventStartTime"), end_raw=m.get("endDate"), event_title=ev.get("title"),
                             group_title=m.get("groupItemTitle")))
    d = pd.DataFrame(rows).drop_duplicates("id")
    d.to_parquet(path)
    return d


def build_markets():
    path = os.path.join(D, "markets.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    cols = ["id", "condition_id", "question", "y", "clean", "start", "end", "closed_time", "event_id", "fee_schedule", "volume"]
    u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=cols)
    u = u[u.question.str.contains("highest temperature", case=False, na=False)]
    u = u[u.closed_time < h001.HOLDOUT_START].copy()        # holdout intacto
    g = scan_gamma()
    u = u.merge(g[["id", "description"]], on="id", how="left")
    p = u.question.map(h014.parse_question)
    u["parsed"] = p.notna()
    u = u[u.parsed].copy()
    P = pd.DataFrame(p.dropna().tolist(), index=u.index)
    u = pd.concat([u, P], axis=1)
    u["station"] = u.description.map(h014.station_from_description)
    u["target"] = [h014.target_date(mo, dy, e) for mo, dy, e in zip(u.month, u.day, u.end)]
    ab = [h014.interval_c(r) for r in u[["lo", "hi", "unit"]].to_dict("records")]
    u["a_c"], u["b_c"] = zip(*ab)
    u["t_dec"] = [h014.decision_time(t) for t in u.target]
    u = u.drop(columns=["description", "parsed"])
    u.to_parquet(path)
    return u


def om_path(st, a, b):
    return os.path.join(OM, f"{st}_{a}_{b}.json")


def fetch_om(st, a, b, tries=400):
    """Open-Meteo Previous Runs (horario, UTC) para la estación `st` en [a, b]. Caché en disco."""
    path = om_path(st, a, b)
    if os.path.exists(path):
        return json.load(open(path))
    lat, lon, _ = h014.STATIONS[st]
    params = {"latitude": lat, "longitude": lon, "start_date": a, "end_date": b, "timezone": "GMT",
              "hourly": "temperature_2m_previous_day1,temperature_2m_previous_day2,temperature_2m_previous_day3"}
    for i in range(tries):
        try:
            r = requests.get("https://previous-runs-api.open-meteo.com/v1/forecast", params=params, timeout=90)
            if r.status_code == 200 and "hourly" in r.json():
                d = r.json()
                tmp = path + ".tmp"
                json.dump(d, open(tmp, "w"))
                os.replace(tmp, path)
                return d
            print(st, a, r.status_code, flush=True)
        except requests.RequestException as e:
            print(st, a, "exc", flush=True)
        time.sleep(4)
    return None


def geocode(cities):
    path = os.path.join(D, "geo.json")
    geo = json.load(open(path)) if os.path.exists(path) else {}
    for c in cities:
        if c in geo:
            continue
        for i in range(8):
            try:
                r = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": c, "count": 1}, timeout=60)
                if r.status_code == 200:
                    res = r.json().get("results") or []
                    geo[c] = res[0] if res else None
                    break
            except requests.RequestException:
                pass
            time.sleep(5 * (i + 1))
    json.dump(geo, open(path, "w"))
    return geo


def ranges(m, chunk=60):
    """{estación: [(a, b), ...]} trozos de ≤ `chunk` días que cubren [primera fecha − 1, última + 1]."""
    g = m.groupby("station").target.agg(["min", "max"])
    out = {}
    for st, r in g.iterrows():
        if st not in h014.STATIONS:
            continue
        a, end = r["min"] - timedelta(days=1), r["max"] + timedelta(days=1)
        out[st] = []
        while a <= end:
            b = min(a + timedelta(days=chunk - 1), end)
            out[st].append((a.isoformat(), b.isoformat()))
            a = b + timedelta(days=1)
    return out


def hourly_dict(d):
    """{ts_utc: {1: v, 2: v, 3: v}} a partir de la respuesta de Open-Meteo."""
    h = d["hourly"]
    out = {}
    for i, t in enumerate(h["time"]):
        ts = int(datetime.fromisoformat(t).replace(tzinfo=timezone.utc).timestamp())
        out[ts] = {k: h[f"temperature_2m_previous_day{k}"][i] for k in (1, 2, 3)}
    return out


def build_forecasts(m):
    ev = m.groupby("event_id").agg(city=("city", "first"), station=("station", "first"), target=("target", "first"),
                                    t_dec=("t_dec", "first"), n_st=("station", "nunique"), n_tg=("target", "nunique")).reset_index()
    R = ranges(m)
    H = {}
    for st, chunks in R.items():
        for a, b in chunks:
            p = om_path(st, a, b)
            if os.path.exists(p):
                H.setdefault(st, {}).update(hourly_dict(json.load(open(p))))
    fc, lead2 = [], []
    for r in ev.itertuples():
        if r.station not in H:
            fc.append(np.nan); lead2.append(np.nan); continue
        tz = ZoneInfo(h014.STATIONS[r.station][2])
        v = h014.daily_max_forecast(H[r.station], tz, r.target, r.t_dec)
        fc.append(np.nan if v is None else v)
        L = h014.leads_used(tz, r.target, r.t_dec)
        lead2.append(np.mean([k >= 2 for k in L]))
    ev["fc"] = fc
    ev["frac_hours_lead_ge2"] = lead2
    ev.to_parquet(os.path.join(D, "forecasts.parquet"))
    return ev


def main_fetch():
    m = build_markets()
    for st, chunks in sorted(ranges(m).items()):
        for a, b in chunks:
            d = fetch_om(st, a, b)
            print(st, a, b, "ok" if d else "FAIL", flush=True)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def main():
    m = build_markets()
    ev = build_forecasts(m)
    geo = geocode(sorted(m.city.unique()))
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    L = ["# H014 G1 — mercados de temperatura máxima vs Open-Meteo (solo entrenamiento)", "",
         f"- commit {commit}; generado por `PYTHONPATH=src python3 experiments/h014_g1.py`",
         f"- datos: data/h014/markets.parquet sha256[:16]={sha(os.path.join(D, 'markets.parquet'))}; "
         f"forecasts.parquet sha256[:16]={sha(os.path.join(D, 'forecasts.parquet'))}", ""]
    # --- universo
    cols = ["id", "question", "closed_time"]
    u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"), columns=cols)
    u = u[u.question.str.contains("highest temperature", case=False, na=False)]
    ntr = int((u.closed_time < h001.HOLDOUT_START).sum())
    L += ["## Universo", "",
          f"- mercados con 'highest temperature' en el universo binario: {len(u):,}; en entrenamiento "
          f"(closedTime < 2026-04-12): {ntr:,}; parseados: {len(m):,} ({len(m)/ntr:.2%}); eventos: {m.event_id.nunique():,}",
          f"- limpios (y∈{{0,1}}): {int(m.clean.sum()):,}; anulados (y=0.5): {int((~m.clean).sum()):,}",
          f"- sin estación identificada: {int(m.station.isna().sum())}; estación sin coordenadas: "
          f"{int((m.station.notna() & ~m.station.isin(list(h014.STATIONS))).sum())}",
          f"- fechas objetivo: {m.target.min()} … {m.target.max()}", "",
          "| unidad | tipo | mercados |", "|---|---|---|"]
    for (un, k), n in m.groupby(["unit", "kind"]).size().items():
        L.append(f"| {un} | {k} | {n:,} |")
    L += ["", "| ciudad | estación(es) | unidad | mercados | eventos | 1ª fecha | última |", "|---|---|---|---|---|---|---|"]
    for c, g in m.groupby("city"):
        L.append(f"| {c} | {', '.join(sorted(g.station.dropna().unique()))} | {', '.join(sorted(g.unit.unique()))} | "
                 f"{len(g):,} | {g.event_id.nunique():,} | {g.target.min()} | {g.target.max()} |")
    # --- validación de coordenadas
    bad = []
    for st, (la, lo, tz) in h014.STATIONS.items():
        cs = m[m.station == st].city.unique()
        for c in cs:
            gg = geo.get(c)
            if not gg:
                bad.append(f"{c}/{st}: sin geocodificación"); continue
            dkm = 6371 * math.acos(min(1, math.sin(math.radians(la)) * math.sin(math.radians(gg["latitude"])) +
                                       math.cos(math.radians(la)) * math.cos(math.radians(gg["latitude"])) *
                                       math.cos(math.radians(lo - gg["longitude"]))))
            if dkm > 60 or gg.get("timezone") != tz:
                bad.append(f"{c}/{st}: {dkm:.0f} km, tz geocod {gg.get('timezone')} vs {tz}")
    L += ["", "## Estaciones", "",
          "- Coordenadas = estación de resolución citada en la descripción (aeropuerto ICAO; Hong Kong Observatory; "
          "estación CWA 46692 de Taipéi), no el centro de la ciudad. Validación contra geocodificación de la ciudad "
          "(distancia ≤ 60 km y misma zona horaria).",
          f"- discrepancias: {len(bad)}" + ("" if not bad else " → " + "; ".join(bad))]
    # --- pronósticos
    cov = ev.fc.notna()
    L += ["", "## Pronóstico (Open-Meteo Previous Runs, best_match)", "",
          f"- eventos con máximo pronosticado: {int(cov.sum()):,} / {len(ev):,} ({cov.mean():.1%})",
          f"- eventos con >1 estación o >1 fecha objetivo dentro del event_id: {int((ev.n_st > 1).sum())} / {int((ev.n_tg > 1).sum())}",
          f"- fracción media de horas del día objetivo con lead ≥ 2 días (sustitución anti-lookahead): "
          f"{ev.frac_hours_lead_ge2.mean():.1%}", "",
          "| ciudad | eventos | con pronóstico |", "|---|---|---|"]
    for c, g in ev.groupby("city"):
        L.append(f"| {c} | {len(g)} | {int(g.fc.notna().sum())} |")
    # --- un YES por evento
    mc = m[m.clean]
    k = mc.groupby("event_id").y.sum()
    nm = m.groupby("event_id").size()
    anul = m.groupby("event_id").clean.apply(lambda s: (~s).any())
    L += ["", "## Resolución: exactamente un tramo YES por evento", "",
          f"- eventos: {len(nm):,}; con exactamente 1 YES: {int((k == 1).sum()):,}; con 0 YES: {int((k == 0).sum()):,}; "
          f"con >1 YES: {int((k > 1).sum()):,}; con algún mercado anulado: {int(anul.sum()):,}",
          f"- mercados por evento: mediana {nm.median():.0f}, min {nm.min()}, max {nm.max()}"]
    # cobertura de tramos: los intervalos del evento deben cubrir la recta real sin solapes
    def cover(g):
        iv = sorted(zip(g.a_c, g.b_c))
        ok = iv[0][0] == -math.inf and iv[-1][1] == math.inf
        ok = ok and all(abs(iv[i][1] - iv[i + 1][0]) < 1e-6 for i in range(len(iv) - 1))
        return ok
    cv = m.groupby("event_id").apply(cover)
    L.append(f"- eventos cuyos tramos forman una partición completa (−∞…∞, sin huecos ni solapes): {int(cv.sum()):,} / {len(cv):,}")
    # --- concordancia pronóstico vs tramo ganador (sanidad, sin PnL)
    win = mc[mc.y == 1][["event_id", "a_c", "b_c", "kind", "unit"]]
    w = win.merge(ev[["event_id", "city", "fc", "target"]], on="event_id")
    w = w[w.fc.notna() & w.event_id.isin(k[k == 1].index)]
    fcr = w.fc
    w["fc_in"] = (fcr >= w.a_c) & (fcr < w.b_c)
    fin = np.isfinite(w.a_c) & np.isfinite(w.b_c)
    w["err"] = np.where(fin, (w.a_c + w.b_c) / 2 - w.fc, np.nan)
    # tramo más probable según el pronóstico puro: el que contiene el pronóstico
    L += ["", "## Sanidad: pronóstico vs tramo ganador (sin PnL)", "",
          f"- eventos con 1 YES y pronóstico: {len(w):,}",
          f"- el tramo que contiene el máximo pronosticado es el ganador: {w.fc_in.mean():.1%}",
          f"- error (centro del tramo ganador − pronóstico, °C, solo tramos interiores, n={int(fin.sum()):,}): "
          f"media {w.err.mean():+.2f}, sd {w.err.std():.2f}, |err|≤1°C {(w.err.abs() <= 1).mean():.1%}", "",
          "| ciudad | n | acierto tramo | media err °C | sd err °C |", "|---|---|---|---|---|"]
    for c, g in w.groupby("city"):
        L.append(f"| {c} | {len(g)} | {g.fc_in.mean():.0%} | {g.err.mean():+.2f} | {g.err.std():.2f} |")
    # --- t de decisión vs creación del mercado
    st_ok = (m.start.astype("int64") // 10**6 <= m.t_dec * 1000)
    L += ["", "## Momento de decisión", "",
          f"- t = 12:00 UTC del día anterior. Mercados creados (startDate) antes de t: {st_ok.mean():.1%}; "
          f"cerrados antes de t: {(m.closed_time.astype('int64') // 10**6 < m.t_dec * 1000).mean():.1%}",
          "", "## Sustituciones respecto al protocolo", "",
          "1. `previous_day1` = valor predicho 24 h antes de cada hora válida. Para horas del día objetivo posteriores a "
          "t + 18 h (24 h − 6 h de publicación) esa predicción se emitió después de t → lookahead. Por hora se usa el menor "
          "lead k ∈ {1,2,3} días con (hora − 24k h + 6 h) ≤ t (la API no ofrece `temperature_2m_max_previous_day1` diario; "
          "el máximo diario se calcula con las horas del día local de la estación). Pesimista: pronóstico algo más viejo.",
          "2. Coordenadas de la estación de resolución (no del centro de la ciudad): el protocolo dice 'coordenadas de la ciudad', "
          "pero la resolución usa la estación; las diferencias son de pocos km.",
          "3. Tramos °F de 2 grados ('between a-b°F') → intervalo [a−0.5, b+0.5) °F; todo convertido a °C.",
          "4. Hong Kong (Observatorio) y Taipéi (CWA) miden con un decimal; se aplica igualmente la semántica de redondeo al entero "
          f"(afecta a {int(m.city.isin(['Hong Kong','Taipei']).sum())} mercados).",
          "5. Modelo de error por ciudad estimado por máxima verosimilitud con censura por intervalos (el observado solo se "
          "conoce como tramo; los extremos son abiertos)."]
    open(os.path.join(ROOT, "reports", "h014_g1.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L[:40]))


if __name__ == "__main__":
    main_fetch() if "--fetch" in sys.argv else main()
