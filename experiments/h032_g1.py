"""H032 G1: universo de eventos semanales de recuento de posts, cobertura de XTracker y concordancia.

    PYTHONPATH=src python3 experiments/h032_g1.py   → reports/h032_g1.md, data/h032/{events,markets}.parquet

- Eventos: mercados de Gamma (data/gamma) de las series en h032.SERIES_HANDLE (+ elon-tweets-48h y
  elon-tweet-daily solo para el recuento informativo). Entrenamiento: TODOS los mercados del evento con
  closedTime < 2026-04-12 (el holdout no se toca).
- Ventana: descripción (horas ET) contrastada con startTime/endDate del evento.
- Concordancia G1: recuento XTracker de [inicio, fin) (createdAt; recuento final, no es feature) frente al
  tramo resuelto (y = 1). Cuentas < 97% se excluyen.
"""
import glob, gzip, hashlib, json, os, subprocess, sys, time
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd, requests
from pmq import h001, h032
from pmq.universe import DATA

D = os.path.join(DATA, "h032")
os.makedirs(D, exist_ok=True)
SERIES = set(h032.SERIES_HANDLE) | {"elon-tweets-48h", "elon-tweet-daily"}
XT = "https://xtracker.polymarket.com/api"
MIN_AGREE = 0.97


# ---------------------------------------------------------------- Gamma
def scan_gamma():
    path = os.path.join(D, "gamma_markets.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    rows = []
    files = sorted(f for f in glob.glob(os.path.join(DATA, "gamma", "win_*.jsonl.gz"))
                   if "2024-05" <= os.path.basename(f)[4:11] and os.path.basename(f)[4:14] <= "2026-10-31")
    for f in files:
        for line in gzip.open(f, "rt"):
            if "seriesSlug" not in line or not any(f'"{s}"' in line for s in SERIES):
                continue
            m = json.loads(line)
            ev = (m.get("events") or [{}])[0]
            if ev.get("seriesSlug") not in SERIES:
                continue
            rows.append(dict(id=str(m["id"]), q=m.get("question"), git=m.get("groupItemTitle"),
                             desc=m.get("description"), event_id=str(ev.get("id")), ev_title=ev.get("title"),
                             series=ev.get("seriesSlug"), ev_start=ev.get("startTime"), ev_end=ev.get("endDate"),
                             tweet_count=ev.get("tweetCount"), g_closed=m.get("closedTime")))
    g = pd.DataFrame(rows).drop_duplicates("id")
    g.to_parquet(path)
    return g


# ---------------------------------------------------------------- XTracker
def ts(x):
    return pd.to_datetime(pd.Series(x), utc=True, format="ISO8601").astype("int64").values // 10**9


def posts(handle):
    """Historial completo de posts de la cuenta (caché gz). Devuelve (created, imported) en s."""
    path = os.path.join(D, f"posts_{handle}.json.gz")
    if not os.path.exists(path):
        for i in range(5):
            try:
                r = requests.get(f"{XT}/users/{handle}/posts", timeout=120,
                                 params={"startDate": "2020-01-01T00:00:00.000Z", "endDate": "2026-10-14T00:00:00.000Z"})
                if r.status_code == 200:
                    d = [{k: p.get(k) for k in ("platformId", "createdAt", "importedAt")} for p in r.json()["data"]]
                    with gzip.open(path + ".tmp", "wt") as f:
                        json.dump(d, f)
                    os.replace(path + ".tmp", path)
                    break
            except requests.RequestException:
                pass
            time.sleep(2 ** i)
    d = json.load(gzip.open(path, "rt"))
    c, i = ts([p["createdAt"] for p in d]), ts([p["importedAt"] for p in d])
    o = np.argsort(c)
    return c[o], i[o]


if __name__ == "__main__":
    g = scan_gamma()
    u = pd.read_parquet(os.path.join(DATA, "universe_binary.parquet"),
                        columns=["id", "condition_id", "y", "clean", "start", "closed_time", "fee_schedule"])
    u["id"] = u.id.astype(str)
    m = g.merge(u, on="id", how="left")
    m["in_universe"] = m.condition_id.notna()
    ev_closed = m.groupby("event_id").closed_time.agg(lambda s: s.max() if s.notna().all() else pd.NaT)
    m["ev_closed"] = m.event_id.map(ev_closed)
    m["train"] = m.ev_closed < h001.HOLDOUT_START
    tr = m[m.train].copy()

    # ventana
    win = tr.drop_duplicates("event_id").set_index("event_id")
    pw = {e: h032.parse_window(d) for e, d in win.desc.items()}
    ev = pd.DataFrame({"series": win.series, "title": win.ev_title, "tweet_count": win.tweet_count})
    ev["start"] = [pw[e][0] if pw[e] else np.nan for e in ev.index]
    ev["end"] = [pw[e][1] if pw[e] else np.nan for e in ev.index]
    es = pd.to_datetime(win.ev_start, utc=True, errors="coerce")
    ee = pd.to_datetime(win.ev_end, utc=True, errors="coerce")
    ev["gamma_start"] = np.where(es.notna(), es.astype("int64") // 10**9, np.nan)
    ev["gamma_end"] = np.where(ee.notna(), ee.astype("int64") // 10**9, np.nan)
    ev["win_match"] = (ev.start == ev.gamma_start) & (ev.end == ev.gamma_end)
    ev["weekly"] = (ev.end - ev.start).between(h032.WEEK_S - 3600, h032.WEEK_S + 3600)  # cambio de hora
    ev["handle"] = ev.series.map(h032.SERIES_HANDLE)
    ev["handle_in_desc"] = [isinstance(h, str) and f"(@{h})".lower() in str(win.desc[e]).lower()
                            for e, h in zip(ev.index, ev.handle)]

    # tramos y resolución
    tr["bucket"] = [h032.parse_bucket(x) for x in tr.git]
    tr["lo"] = [b[0] if b else np.nan for b in tr.bucket]
    tr["hi"] = [(b[1] if b[1] is not None else np.inf) if b else np.nan for b in tr.bucket]
    grp = tr.groupby("event_id")
    ev["n_mk"] = grp.size()
    ev["all_in_universe"] = grp.in_universe.all()
    ev["buckets_ok"] = grp.bucket.agg(lambda s: s.notna().all() and h032.buckets_partition(list(s)))
    ev["n_yes"] = grp.y.agg(lambda s: int((s == 1).sum()))
    ev["all_clean"] = grp.clean.agg(lambda s: bool(s.fillna(False).all()))
    yes = tr[tr.y == 1].drop_duplicates("event_id").set_index("event_id")
    ev["res_lo"], ev["res_hi"] = yes.lo, yes.hi

    # XTracker
    hist = {}
    cov = []
    for h in sorted(set(h032.SERIES_HANDLE.values())):
        c, i = posts(h)
        hist[h] = (c, i)
        cov.append(dict(handle=h, posts=len(c), first_created=pd.to_datetime(c[0], unit="s", utc=True),
                        first_imported=pd.to_datetime(i.min(), unit="s", utc=True),
                        last_created=pd.to_datetime(c[-1], unit="s", utc=True),
                        lag_med_s=float(np.median(i - c)),
                        lag_p95_s=float(np.percentile(i - c, 95)),
                        lag_after_first_import_p95_s=float(np.percentile((i - c)[c > i.min()], 95))))
    cov = pd.DataFrame(cov).set_index("handle")
    ev["first_created"] = ev.handle.map(lambda h: hist[h][0][0] if h in hist else np.nan)
    ev["first_imported"] = ev.handle.map(lambda h: hist[h][1].min() if h in hist else np.nan)
    ev["xt_window_covered"] = ev.first_created <= ev.start
    ev["xt_count"] = [h032.final_count(hist[h][0], s, e) if (h in hist and s == s) else np.nan
                      for h, s, e in zip(ev.handle, ev.start, ev.end)]
    ev["agree"] = (ev.xt_count >= ev.res_lo) & (ev.xt_count <= ev.res_hi)
    ev["gamma_count_agree"] = (ev.tweet_count >= ev.res_lo) & (ev.tweet_count <= ev.res_hi)
    ev["t"] = ev.start + h032.DEC_OFFSET_S
    ev["R"] = ev.end - ev.t
    ev["hist_ok"] = [bool(h032.history_ok(fi, fc, s, t, R)) if fi == fi and s == s else False
                     for fi, fc, s, t, R in zip(ev.first_imported, ev.first_created, ev.start, ev.t, ev.R)]
    base = (ev.handle.notna() & ev.weekly & ev.handle_in_desc & ev.buckets_ok & (ev.n_yes == 1)
            & ev.all_in_universe & ev.all_clean)
    chk = ev[base & ev.xt_window_covered]
    acc = chk.groupby("handle").agg(n=("agree", "size"), agree=("agree", "mean"),
                                    gamma_agree=("gamma_count_agree", "mean"),
                                    med_abs_diff=("xt_count", lambda s: np.nan))
    acc["med_abs_diff"] = chk.assign(d=(chk.xt_count - chk.tweet_count).abs()).groupby("handle").d.median()
    acc["pass"] = acc.agree >= MIN_AGREE
    ok_handles = set(acc.index[acc["pass"]])
    ev["account_ok"] = ev.handle.isin(ok_handles)
    ev["usable"] = base & ev.account_ok & ev.hist_ok
    ev.to_parquet(os.path.join(D, "events.parquet"))
    keep = ["id", "condition_id", "q", "git", "event_id", "series", "lo", "hi", "y", "clean", "start", "closed_time",
            "fee_schedule"]
    tr[keep].rename(columns={"start": "mk_start"}).to_parquet(os.path.join(D, "markets.parquet"))

    # ---------------------------------------------------------------- informe
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    allev = m.drop_duplicates("event_id")
    L = ["# H032 G1 — eventos de recuento de posts y cobertura de XTracker (solo entrenamiento)", "",
         f"- commit {commit}; `PYTHONPATH=src python3 experiments/h032_g1.py`; gamma_markets.parquet "
         f"{sha(os.path.join(D, 'gamma_markets.parquet'))}; posts XTracker descargados 2026-10-14 "
         + ", ".join(f"{h} {sha(os.path.join(D, f'posts_{h}.json.gz'))}" for h in sorted(hist)),
         f"- entrenamiento = todos los mercados del evento con closedTime < {h001.HOLDOUT_START.date()}. "
         f"Eventos de las series en total: {allev.event_id.nunique()}; en entrenamiento: {len(ev)}; "
         f"excluidos por tener algún mercado en holdout o sin cerrar: {allev.event_id.nunique() - len(ev)}.",
         "", "## Eventos por serie (entrenamiento)", "",
         "| serie | eventos | semanales (7 d) | ventana = Gamma | handle en descripción | tramos partición | 1 YES | limpios | ventana cubierta por XTracker | historial ok en t | utilizables |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s, x in ev.groupby("series"):
        L.append(f"| {s} | {len(x)} | {int(x.weekly.sum())} | {int(x.win_match.sum())} | {int(x.handle_in_desc.sum())} | "
                 f"{int(x.buckets_ok.sum())} | {int((x.n_yes == 1).sum())} | {int(x.all_clean.sum())} | "
                 f"{int(x.xt_window_covered.sum())} | {int(x.hist_ok.sum())} | {int(x.usable.sum())} |")
    L += ["", "## Cobertura del historial de XTracker", "",
          "| handle | posts | primer createdAt | primer importedAt | último createdAt | retraso importación mediana (s) | p95 (s) | p95 tras 1.ª importación (s) |",
          "|---|---|---|---|---|---|---|---|"]
    for h, r in cov.iterrows():
        L.append(f"| {h} | {r.posts:,} | {r.first_created:%Y-%m-%d %H:%M} | {r.first_imported:%Y-%m-%d %H:%M} | "
                 f"{r.last_created:%Y-%m-%d} | {r.lag_med_s:,.0f} | {r.lag_p95_s:,.0f} | {r.lag_after_first_import_p95_s:,.0f} |")
    L += ["", "Antes del primer importedAt los posts son de carga retroactiva (no conocidos en tiempo real); la regla "
          "importedAt ≤ t los excluye. Un evento es utilizable solo si el tracker ya importaba al empezar la ventana y "
          "hay ≥ 8·R (R = fin − t ≈ 3 días) de historial (createdAt) antes de t.", "",
          "## Concordancia recuento XTracker vs tramo resuelto", "",
          "Eventos semanales limpios con 1 YES, tramos que particionan 0..∞ y ventana completa dentro del historial.", "",
          "| handle | eventos | concordancia XTracker | concordancia tweetCount de Gamma | mediana |XTracker − tweetCount| | pasa (≥ 97%) |",
          "|---|---|---|---|---|---|"]
    for h, r in acc.iterrows():
        L.append(f"| {h} | {int(r.n)} | {r.agree:.1%} | {r.gamma_agree:.1%} | {r.med_abs_diff:.0f} | {'sí' if r['pass'] else 'NO'} |")
    bad = chk[~chk.agree]
    if len(bad):
        L += ["", "Discrepancias:", "", "| evento | handle | ventana (UTC) | XTracker | tweetCount Gamma | tramo resuelto |", "|---|---|---|---|---|---|"]
        for e, r in bad.iterrows():
            hi = "∞" if r.res_hi == np.inf else int(r.res_hi)
            L.append(f"| {r.title} | {r.handle} | {pd.to_datetime(r.start, unit='s'):%m-%d %H:%M} | {int(r.xt_count)} | "
                     f"{r.tweet_count} | {int(r.res_lo)}–{hi} |")
    us = ev[ev.usable]
    L += ["", "## Eventos utilizables para G2", "",
          f"- **{len(us)} eventos** en {us.handle.nunique()} cuentas: " +
          ", ".join(f"{h} {n}" for h, n in us.handle.value_counts().items()),
          f"- rango de ventanas: {pd.to_datetime(us.start.min(), unit='s'):%Y-%m-%d} … {pd.to_datetime(us.end.max(), unit='s'):%Y-%m-%d}",
          f"- {'< 150 eventos: G4 (≥ 150 mercados independientes OOS) es INVIABLE con el entrenamiento; G2 se reporta igualmente.' if len(us) < 150 else '≥ 150 eventos.'}",
          "", "## Notas y sustituciones", "",
          "1. Solo ventanas semanales (7 días): las series elon-tweets-48h (ventana 2 días) y elon-tweet-daily "
          "(mensual) no admiten t = inicio + 4 días con el mismo diseño; se excluyen (pre-registro: 'semanales').",
          "2. Las ventanas solapadas de Elon (martes–martes y viernes–viernes) son eventos distintos pero correlacionados; "
          "G2 los trata como clusters separados (cuenta-semana) y además informa el bootstrap por cuenta-mes.",
          "3. Recuento XTracker con createdAt en [inicio, fin) usando el historial actual de la API (recuento final; solo "
          "para G1). La concordancia con < 34 eventos solo puede pasar con 100%."]
    open(os.path.join(ROOT, "reports", "h032_g1.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
