"""H027 G1 (solo entrenamiento, closedTime < 2026-04-12): METAR (IEM ASOS) vs tramo resuelto.

    PYTHONPATH=src python3 experiments/h027_g1.py --fetch   # descarga METAR (secuencial, caché)
    PYTHONPATH=src python3 experiments/h027_g1.py           # → reports/h027_g1.md, data/h027/events.parquet

Usa data/h014/markets.parquet (construido por experiments/h014_g1.py; solo entrenamiento).
METAR: https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py, data=tmpf, tz=UTC, report_type=3,4
(rutinarios y especiales). Caché en data/h027/metar/<ICAO>.csv.
"""
import hashlib, io, json, os, subprocess, sys, time
from datetime import timedelta
from zoneinfo import ZoneInfo
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd, requests
from pmq import h014, h027
from pmq.universe import DATA

D = os.path.join(DATA, "h027")
MET = os.path.join(D, "metar")
os.makedirs(MET, exist_ok=True)
URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"


def markets():
    m = pd.read_parquet(os.path.join(DATA, "h014", "markets.parquet"))
    assert (m.closed_time < pd.Timestamp("2026-04-12", tz="UTC")).all()   # holdout intacto
    return m


def metar_path(st):
    return os.path.join(MET, f"{st}.csv")


def fetch_station(st, a, b, tries=30):
    path = metar_path(st)
    if os.path.exists(path):
        return True
    params = {"station": st, "data": "tmpf", "tz": "UTC", "format": "onlycomma", "missing": "empty",
              "report_type": "3,4", "sts": f"{a}T00:00Z", "ets": f"{b}T00:00Z"}
    for i in range(tries):
        try:
            r = requests.get(URL, params=params, timeout=300)
            if r.status_code == 200 and r.text.startswith("station"):
                tmp = path + ".tmp"
                open(tmp, "w").write(r.text)
                os.replace(tmp, path)
                return True
            print(st, r.status_code, r.text[:100], flush=True)
        except requests.RequestException as e:
            print(st, "exc", repr(e)[:100], flush=True)
        time.sleep(10 * (i + 1))
    return False


def main_fetch():
    m = markets()
    g = m[~m.station.isin(h027.NO_METAR)].groupby("station").target.agg(["min", "max"])
    for st, r in g.iterrows():
        a, b = r["min"] - timedelta(days=2), r["max"] + timedelta(days=2)
        ok = fetch_station(st, a.isoformat(), b.isoformat())
        print(st, a, b, "ok" if ok else "FAIL", flush=True)
        time.sleep(2)


def load_obs(st):
    """(ts epoch UTC int64, tmpf float) sin valores vacíos, ordenado."""
    p = metar_path(st)
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p)
    d = d[pd.to_numeric(d.tmpf, errors="coerce").notna()]
    ts = (pd.to_datetime(d.valid, utc=True) - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(seconds=1)
    o = pd.DataFrame({"ts": ts.values, "tmpf": d.tmpf.astype(float).values}).sort_values("ts")
    return o.drop_duplicates()


def build_events(m):
    """Una fila por evento: ciudad, estación, unidad, fecha, t, M (15:00 − 15 min), máximo final METAR."""
    ev = m.groupby("event_id").agg(city=("city", "first"), station=("station", "first"), unit=("unit", "first"),
                                    target=("target", "first"), n_st=("station", "nunique"),
                                    n_unit=("unit", "nunique")).reset_index()
    cache, rows = {}, []
    for r in ev.itertuples():
        st = r.station
        if st not in cache:
            cache[st] = None if st in h027.NO_METAR else load_obs(st)
        o = cache[st]
        tz = ZoneInfo(h014.STATIONS[st][2])
        t = h027.decision_ts(tz, r.target)
        if o is None or r.n_unit > 1 or r.n_st > 1:
            rows.append((t, None, None, 0)); continue
        d0, d1 = h027.local_day(tz, r.target)
        k = (o.ts.values >= d0 - 86400) & (o.ts.values < d1 + 86400)
        ts = o.ts.values[k]
        v = np.array([h027.to_unit(x, r.unit) for x in o.tmpf.values[k]], dtype=int)
        _, M = h027.nowcast_state(ts, v, tz, r.target)
        X = h027.final_max(ts, v, tz, r.target)
        rows.append((t, M, X, h027.n_hours(ts, d0, d1 - 1)))
    ev["t_dec"], ev["M"], ev["Xmax"], ev["hours_day"] = zip(*rows)
    for c in ("M", "Xmax"):
        ev[c] = pd.to_numeric(ev[c], errors="coerce")
    return ev


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]


def main():
    m = markets()
    ev = build_events(m)
    # tramo ganador (eventos limpios con exactamente un YES)
    w = m[m.clean & (m.y == 1)]
    nyes = m[m.clean].groupby("event_id").y.sum()
    w = w[w.event_id.isin(nyes[nyes == 1].index)]
    w = w.assign(ia=[h027.bucket_ints(k, a, b)[0] for k, a, b in zip(w.kind, w.lo, w.hi)],
                 ib=[h027.bucket_ints(k, a, b)[1] for k, a, b in zip(w.kind, w.lo, w.hi)])
    ev = ev.merge(w[["event_id", "ia", "ib"]], on="event_id", how="left")
    ok = ev.Xmax.notna() & ev.ia.notna()
    ev["agree"] = np.where(ok, (ev.Xmax >= ev.ia) & (ev.Xmax <= ev.ib), np.nan)
    ev["miss"] = np.where(ok, np.where(ev.Xmax < ev.ia, ev.Xmax - ev.ia, np.where(ev.Xmax > ev.ib, ev.Xmax - ev.ib, 0)), np.nan)
    ag = ev[ok].groupby("city").agg(n=("agree", "size"), agree=("agree", "mean"), stations=("station", lambda s: ",".join(sorted(set(s)))))
    allc = ev.groupby("city").agg(events=("event_id", "size"), metar=("Xmax", lambda s: int(s.notna().sum())),
                                  withM=("M", lambda s: int(s.notna().sum())))
    ag = allc.join(ag, how="left")
    ag["included"] = ag.agree >= h027.MIN_AGREE
    ev["city_ok"] = ev.city.map(ag.included).fillna(False).astype(bool) & ~ev.station.isin(h027.NO_METAR)
    ev.to_parquet(os.path.join(D, "events.parquet"))
    json.dump(sorted(ag[ag.included].index.tolist()), open(os.path.join(D, "cities_ok.json"), "w"))

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    files = sorted(f for f in os.listdir(MET) if f.endswith(".csv"))
    hsh = hashlib.sha256(b"".join(open(os.path.join(MET, f), "rb").read() for f in files)).hexdigest()[:16]
    oka = ev[ok]
    L = ["# H027 G1 — máximo diario METAR vs tramo resuelto (solo entrenamiento)", "",
         f"- commit {commit}; `PYTHONPATH=src python3 experiments/h027_g1.py --fetch` y luego sin argumentos",
         f"- datos: data/h014/markets.parquet sha256[:16]={sha(os.path.join(DATA, 'h014', 'markets.parquet'))}; "
         f"METAR IEM ({len(files)} estaciones, data/h027/metar/*.csv) sha256[:16] concatenado={hsh}",
         f"- eventos de entrenamiento: {len(ev):,}; con máximo METAR válido (≥ {h027.MIN_HOURS_DAY} h con observación) y "
         f"exactamente un tramo YES: {int(ok.sum()):,}; con M válido a las 15:00 − 15 min: {int(ev.M.notna().sum()):,}",
         f"- concordancia global: {oka.agree.mean():.2%}; fallos por debajo del tramo {int((oka.miss < 0).sum())}, por encima "
         f"{int((oka.miss > 0).sum())}; |desvío| = 1 unidad en {int((oka.miss.abs() == 1).sum())} de "
         f"{int((oka.miss != 0).sum())} fallos",
         f"- regla: ciudad incluida si concordancia ≥ {h027.MIN_AGREE:.0%} (pre-registrado). Incluidas: "
         f"{int(ag.included.sum())} de {len(ag)}", "",
         "| ciudad | estación(es) METAR | eventos | con máx. METAR | con M | n G1 | concordancia | incluida |",
         "|---|---|---|---|---|---|---|---|"]
    for c, r in ag.sort_index().iterrows():
        L.append(f"| {c} | {r.stations if isinstance(r.stations, str) else '—'} | {r.events} | {r.metar} | {r.withM} | "
                 f"{0 if pd.isna(r.n) else int(r.n)} | {'—' if pd.isna(r.agree) else f'{r.agree:.1%}'} | "
                 f"{'sí' if r.included else 'NO'} |")
    inc = ev[ev.city_ok]
    L += ["", "## Ciudades incluidas", "",
          f"- eventos de ciudades incluidas: {len(inc):,}; con M válido: {int(inc.M.notna().sum()):,}; "
          f"mercados: {int(m.event_id.isin(inc.event_id).sum()):,}",
          f"- R = máximo final − M (unidad del mercado), ciudades incluidas: " +
          ", ".join(f"{k}: {v:.1%}" for k, v in (inc.Xmax - inc.M).dropna().astype(int).clip(upper=5)
                    .value_counts(normalize=True).sort_index().items()) + " (5 = ≥5)",
          "", "## Sustituciones y decisiones", "",
          "1. Máximo diario = máximo de todas las observaciones METAR rutinarias y especiales (report_type 3,4) del día local "
          "de la estación, redondeado a entero en la unidad del mercado (°F: tmpf de IEM, que en EE. UU. ya viene en °F "
          "enteros; °C: el grupo entero del METAR). No se usan los grupos de máximas de 6 h (1sTTT), que Wunderground no "
          "muestra en su tabla horaria.",
          "2. Hong Kong (Observatorio, HKO) y Taipéi (CWA 46692) resuelven con estaciones sin METAR: esos mercados se "
          "excluyen (no se sustituyen por el aeropuerto, que mide otra cosa). La concordancia de Hong Kong/Taipéi se "
          "calcula solo con sus eventos resueltos por aeropuerto (VHHH, RCSS, RCTP).",
          f"3. Calidad mínima (fijada antes de ver resultados): máximo final con ≥ {h027.MIN_HOURS_DAY} horas con "
          f"observación; M con ≥ {h027.MIN_HOURS_CUM} horas en [00:00, t−15 min] y alguna observación en las 2 h previas "
          "a t−15 min.",
          "4. Eventos con >1 estación o >1 unidad dentro del event_id se descartan (no hay ninguno con >1 unidad salvo "
          "que se indique arriba)."]
    open(os.path.join(ROOT, "reports", "h027_g1.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main_fetch() if "--fetch" in sys.argv else main()
