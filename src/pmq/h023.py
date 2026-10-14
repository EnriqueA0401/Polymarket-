"""H023 — Lead-lag Kalshi → Polymarket en partidos NFL/NBA/MLB (pre-partido).

Protocolo G0 (HYPOTHESES.md, fijado antes de ver datos):
  señal en t (un trade de Kalshi): |K(t) − K(t−120 s)| ≥ 0.05 y |PM(t) − PM(t−120 s)| < 0.02,
  con K/PM = último precio negociado (probabilidad del equipo de referencia) a cada instante,
  solo antes del inicio del partido. Entrada: peor compra taker real en PM del lado del movimiento
  en (t+30 s, t+300 s]; se mantiene hasta resolución; comisión vigente.

Decisiones de implementación (fijadas antes de ver resultados; documentadas en reports/h023_g*.md):
  - Equipo de referencia = outcome0 de Polymarket; serie de Kalshi = el mercado "<equipo outcome0> wins"
    (un solo mercado de Kalshi por partido: mezclar los dos mercados crearía saltos falsos del tamaño
    del spread).
  - Todo el ciclo (señal + ventana de entrada) debe ser pre-partido: t + 300 s ≤ gameStartTime.
  - PM(t−120) debe existir (algún trade PM en la hora anterior); si no, no hay señal (no se puede
    afirmar que PM no se movió).
  - Periodo refractario: tras una señal en un partido, la siguiente solo si t' ≥ t + 300 s.
"""
import glob, gzip, json, os, re, threading, time
import numpy as np
import pandas as pd
import requests

from pmq.universe import DATA

HOLDOUT_START = pd.Timestamp("2026-04-12", tz="UTC")
K_API = "https://api.elections.kalshi.com/trade-api/v2"
CACHE = os.path.join(DATA, "h023")

WIN, K_MOVE, PM_MAX = 120, 0.05, 0.02         # ventana 2 min, umbral Kalshi, umbral PM
ENTRY_LAG, ENTRY_END = 30, 300                  # (t+30 s, t+5 min]
PM_LOOKBACK = 3600                              # para conocer el último precio PM en t−120
REFRACTORY = 300

LEAGUES = {  # liga → (serie Kalshi, series PM)
    "NFL": ("KXNFLGAME", ("nfl", "nfl-2025", "nfl-2026")),
    "NBA": ("KXNBAGAME", ("nba", "nba-2026")),
    "MLB": ("KXMLBGAME", ("mlb", "mlb-games")),
}

# ---------------------------------------------------------------------------------------------
# Tabla de emparejamiento versionada: código de Kalshi (sufijo del ticker) → nombre completo del
# equipo tal como aparece en la descripción de Polymarket ("If <nombre completo> wins, ...").
# Construida a mano a partir de los 32/30/30 códigos observados en los mercados de Kalshi.
# ---------------------------------------------------------------------------------------------
TEAMS = {
    "NFL": {
        "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
        "CAR": "Carolina Panthers", "CHI": "Chicago Bears", "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns",
        "DAL": "Dallas Cowboys", "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
        "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAC": "Jacksonville Jaguars",
        "KC": "Kansas City Chiefs", "LA": "Los Angeles Rams", "LAC": "Los Angeles Chargers",
        "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
        "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
        "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
        "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
        "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
    },
    "NBA": {
        "ATL": "Atlanta Hawks", "BKN": "Brooklyn Nets", "BOS": "Boston Celtics", "CHA": "Charlotte Hornets",
        "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers", "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets",
        "DET": "Detroit Pistons", "GSW": "Golden State Warriors", "HOU": "Houston Rockets",
        "IND": "Indiana Pacers", "LAC": "Los Angeles Clippers", "LAL": "Los Angeles Lakers",
        "MEM": "Memphis Grizzlies", "MIA": "Miami Heat", "MIL": "Milwaukee Bucks",
        "MIN": "Minnesota Timberwolves", "NOP": "New Orleans Pelicans", "NYK": "New York Knicks",
        "OKC": "Oklahoma City Thunder", "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers",
        "PHX": "Phoenix Suns", "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings",
        "SAS": "San Antonio Spurs", "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
    },
    "MLB": {
        "ARI": "Arizona Diamondbacks", "AZ": "Arizona Diamondbacks", "ATH": "Athletics",
        "ATL": "Atlanta Braves", "BAL": "Baltimore Orioles", "BOS": "Boston Red Sox", "CHC": "Chicago Cubs",
        "CIN": "Cincinnati Reds", "CLE": "Cleveland Guardians", "COL": "Colorado Rockies",
        "CWS": "Chicago White Sox", "DET": "Detroit Tigers", "HOU": "Houston Astros",
        "KC": "Kansas City Royals", "LAA": "Los Angeles Angels", "LAD": "Los Angeles Dodgers",
        "MIA": "Miami Marlins", "MIL": "Milwaukee Brewers", "MIN": "Minnesota Twins", "NYM": "New York Mets",
        "NYY": "New York Yankees", "PHI": "Philadelphia Phillies", "PIT": "Pittsburgh Pirates",
        "SD": "San Diego Padres", "SEA": "Seattle Mariners", "SF": "San Francisco Giants",
        "STL": "St. Louis Cardinals", "TB": "Tampa Bay Rays", "TEX": "Texas Rangers",
        "TOR": "Toronto Blue Jays", "WSH": "Washington Nationals",
    },
}
# alias de nombre completo en PM (la descripción a veces usa otra forma)
PM_ALIAS = {"Oakland Athletics": "Athletics", "Sacramento Athletics": "Athletics", "LA Clippers": "Los Angeles Clippers"}


def norm_team(name):
    name = re.sub(r"\s+", " ", (name or "").strip())
    return PM_ALIAS.get(name, name)


# ---------------------------------------------------------------------------------------------
# Polymarket: mercados moneyline con gameStartTime (desde el JSON crudo de Gamma)
# ---------------------------------------------------------------------------------------------
DESC_RE = re.compile(r"If (?:the )?(.+?) wins?,? (?:the )?market will resolve to [\"“](.+?)[\"”]")


def canon(name, league):
    """Nombre completo canónico del equipo: exacto, alias o sufijo único (apodo, p. ej. 'Clippers').
    None si no se reconoce o es ambiguo."""
    name = norm_team(name)
    full = set(TEAMS[league].values())
    if name in full:
        return name
    hits = [f for f in full if f.endswith(" " + name) or f == name]
    return hits[0] if len(hits) == 1 else None


def pm_full_names(desc, outcomes, league):
    """Nombres completos de los dos outcomes: primero la descripción ('If X wins … resolve to “o”'),
    si no, el propio outcome como apodo. None si alguno no se reconoce."""
    found = {o.strip(): full for full, o in DESC_RE.findall(desc or "")}
    out = [canon(found.get(o, o), league) or canon(o, league) for o in outcomes]
    return None if None in out else out


def extract_pm(out_path, first="2025-03-01", last="2026-12-31"):
    """Escanea data/gamma y guarda los moneyline de las series de LEAGUES (dedup por id)."""
    series = {s: lg for lg, (_, ss) in LEAGUES.items() for s in ss}
    rows = {}
    for f in sorted(glob.glob(os.path.join(DATA, "gamma", "win_*.jsonl.gz"))):
        day = os.path.basename(f)[4:14]
        if not (first <= day <= last):
            continue
        with gzip.open(f, "rt") as fh:
            for line in fh:
                if "gameStartTime" not in line or " vs" not in line:
                    continue
                m = json.loads(line)
                ev = (m.get("events") or [{}])[0]
                lg = series.get(ev.get("seriesSlug"))
                if lg is None:
                    continue
                q = m.get("question") or ""
                smt = m.get("sportsMarketType")
                if smt not in (None, "moneyline") or ":" in q or " vs" not in q:
                    continue
                try:
                    outs = json.loads(m.get("outcomes") or "[]")
                except ValueError:
                    continue
                if len(outs) != 2:
                    continue
                rows[int(m["id"])] = {
                    "id": int(m["id"]), "league": lg, "question": q, "slug": m.get("slug"),
                    "o0": outs[0], "o1": outs[1], "smt": smt, "description": (m.get("description") or "")[:600],
                    "game_start": m.get("gameStartTime"), "series": ev.get("seriesSlug")}
    df = pd.DataFrame(list(rows.values()))
    df["game_start"] = pd.to_datetime(df.game_start, utc=True, errors="coerce", format="mixed")
    df.to_parquet(out_path)
    return df


# ---------------------------------------------------------------------------------------------
# Kalshi: mercados y trades (API pública, caché en disco)
# ---------------------------------------------------------------------------------------------
_last = [0.0]
_lock = threading.Lock()


def k_get(path, params, tries=10, min_gap=0.1):
    """GET con límite global de ritmo (seguro entre hilos) y reintentos con espera exponencial."""
    for i in range(tries):
        with _lock:
            dt = time.time() - _last[0]
            if dt < min_gap:
                time.sleep(min_gap - dt)
            _last[0] = time.time()
        try:
            r = requests.get(K_API + path, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
        except requests.RequestException:
            pass
        time.sleep(min(30, 1.0 * 2 ** i))
    raise RuntimeError(f"Kalshi {path} {params} falló")


def k_markets(series):
    """Todos los mercados liquidados de la serie (histórico + recientes). Caché."""
    path = os.path.join(CACHE, f"markets_{series}.json.gz")
    if os.path.exists(path):
        return json.load(gzip.open(path, "rt"))
    out = []
    for ep, extra in (("/historical/markets", {}), ("/markets", {"status": "settled"})):
        cur = None
        while True:
            q = {"series_ticker": series, "limit": 1000, **extra}
            if cur:
                q["cursor"] = cur
            d = k_get(ep, q)
            out += d.get("markets", [])
            cur = d.get("cursor")
            if not cur or not d.get("markets"):
                break
    seen, ded = set(), []
    for m in out:
        if m["ticker"] not in seen:
            seen.add(m["ticker"]); ded.append(m)
    json.dump(ded, gzip.open(path, "wt"))
    return ded


K_KEEP = ("created_time", "yes_price_dollars", "count_fp", "taker_side")


def k_trades(ticker, min_ts, max_ts, historical=True):
    """Trades públicos de un mercado de Kalshi en [min_ts, max_ts] (unix s). Caché por ticker."""
    d = os.path.join(CACHE, "ktrades")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{ticker}_{min_ts}_{max_ts}.json.gz")
    if os.path.exists(path):
        try:
            return json.load(gzip.open(path, "rt"))
        except (OSError, EOFError, ValueError):
            os.remove(path)
    ep = "/historical/trades" if historical else "/markets/trades"
    out, cur = [], None
    while True:
        q = {"ticker": ticker, "min_ts": int(min_ts), "max_ts": int(max_ts), "limit": 1000}
        if cur:
            q["cursor"] = cur
        r = k_get(ep, q)
        if r is None:
            break
        out += [{k: x.get(k) for k in K_KEEP} for x in r.get("trades", [])]
        cur = r.get("cursor")
        if not cur or not r.get("trades"):
            break
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt") as f:
        json.dump(out, f)
    os.replace(tmp, path)
    return out


def k_series(trades):
    """(ts unix float, precio YES) ordenados por tiempo."""
    if not trades:
        return np.zeros(0), np.zeros(0)
    ts = pd.to_datetime([x["created_time"] for x in trades], utc=True, format="mixed")
    t = ts.as_unit("ns").asi8 / 1e9
    p = np.array([float(x["yes_price_dollars"]) for x in trades])
    o = np.argsort(t, kind="stable")
    return t[o], p[o]


# ---------------------------------------------------------------------------------------------
# Emparejamiento
# ---------------------------------------------------------------------------------------------
def k_events(markets, league):
    """Una fila por evento de Kalshi con ambos equipos (nombre completo), resultado y fecha."""
    rows = {}
    for m in markets:
        code = m["ticker"].split("-")[-1]
        name = TEAMS[league].get(code)
        e = rows.setdefault(m["event_ticker"], {"event_ticker": m["event_ticker"], "league": league, "mk": {}})
        e["mk"][name] = {"ticker": m["ticker"], "result": m.get("result"), "close": m.get("close_time"),
                         "open": m.get("open_time"), "settle": m.get("settlement_value_dollars")}
    out = []
    for e in rows.values():
        if None in e["mk"] or len(e["mk"]) != 2:
            continue
        m = re.match(r"^[A-Z]+-(\d{2})([A-Z]{3})(\d{2})", e["event_ticker"])
        if not m:
            continue
        date = pd.to_datetime(f"20{m.group(1)}-{m.group(2)}-{m.group(3)}", format="%Y-%b-%d").date()
        out.append({**e, "date": date, "teams": frozenset(e["mk"])})
    return out


def match(pm, kev):
    """Empareja mercados PM (cols id, league, o0, o1, description, game_start) con eventos Kalshi
    por (liga, fecha ET de gameStartTime, conjunto de equipos). Ambigüedad → excluido.
    Devuelve DataFrame con status ∈ {ok, no_names, no_kalshi, ambiguous}."""
    idx = {}
    for e in kev:
        idx.setdefault((e["league"], e["date"], e["teams"]), []).append(e)
    out = []
    for r in pm.itertuples(index=False):
        names = pm_full_names(r.description, [r.o0, r.o1], r.league)
        base = {"id": r.id, "league": r.league, "status": None, "team0": None, "team1": None,
                "k_event": None, "k_ticker0": None, "k_result0": None, "k_close": None}
        if names is None or pd.isna(r.game_start) or names[0] == names[1]:
            out.append({**base, "status": "no_names"}); continue
        d = r.game_start.tz_convert("America/New_York").date()
        cands = idx.get((r.league, d, frozenset(names)), [])
        if not cands:
            out.append({**base, "status": "no_kalshi", "team0": names[0], "team1": names[1]}); continue
        if len(cands) > 1:
            out.append({**base, "status": "ambiguous", "team0": names[0], "team1": names[1]}); continue
        e = cands[0]
        mk = e["mk"][names[0]]
        out.append({**base, "status": "ok", "team0": names[0], "team1": names[1], "k_event": e["event_ticker"],
                    "k_ticker0": mk["ticker"], "k_result0": mk["result"], "k_close": mk["close"],
                    "k_open": mk["open"]})
    return pd.DataFrame(out)


def k_y(result):
    return {"yes": 1.0, "no": 0.0}.get(result, np.nan)


# ---------------------------------------------------------------------------------------------
# Señal y decisión (solo datos ≤ t)
# ---------------------------------------------------------------------------------------------
def last_price(t_arr, p_arr, t):
    """Último precio con timestamp ≤ t (NaN si no hay)."""
    i = np.searchsorted(t_arr, t, side="right") - 1
    return p_arr[i] if i >= 0 else np.nan


def pm_series(trades):
    """Serie del precio de outcome0 en PM a partir de trades taker (token 1 → 1 − precio)."""
    if not trades:
        return np.zeros(0), np.zeros(0)
    t = np.array([float(x["timestamp"]) for x in trades])
    p = np.array([float(x["price"]) if x["outcomeIndex"] == 0 else 1 - float(x["price"]) for x in trades])
    o = np.argsort(t, kind="stable")
    return t[o], p[o]


def k_candidates(kt, kp, game_start, shift=0.0):
    """Instantes t (trades de Kalshi, desplazados `shift` s) con |K(t) − K(t−WIN)| ≥ K_MOVE y
    t + ENTRY_END ≤ game_start. Devuelve lista de (t, dK). Sin periodo refractario aquí."""
    t_all = kt + shift
    out = []
    for i, t in enumerate(t_all):
        if t + ENTRY_END > game_start:
            break
        j = np.searchsorted(t_all, t, side="right") - 1      # último trade ≤ t (incluye simultáneos)
        k0 = last_price(t_all, kp, t - WIN)
        if np.isnan(k0):
            continue
        dk = kp[j] - k0
        if abs(dk) >= K_MOVE - 1e-9:
            out.append((float(t), float(dk)))
    return out


def signals(cands, pt, pp):
    """Filtra candidatos con PM quieto: |PM(t) − PM(t−WIN)| < PM_MAX y PM(t−WIN) conocido
    (último trade en [t−WIN−PM_LOOKBACK, t−WIN]). Aplica periodo refractario. Solo usa PM ≤ t."""
    out, last_sig = [], -np.inf
    for t, dk in cands:
        if t < last_sig + REFRACTORY:
            continue
        i0 = np.searchsorted(pt, t - WIN, side="right") - 1
        if i0 < 0 or pt[i0] < t - WIN - PM_LOOKBACK:
            continue
        p0, p1 = pp[i0], last_price(pt, pp, t)
        if abs(p1 - p0) < PM_MAX - 1e-9:
            out.append({"t": t, "dk": dk, "pm0": p0, "pm1": p1, "idx": 0 if dk > 0 else 1})
            last_sig = t
    return out


def exec_price(trades, idx, t0, t1):
    """Peor (máximo) precio pagado por takers compradores del token idx en (t0, t1]."""
    px = [float(x["price"]) for x in trades or []
          if x["outcomeIndex"] == idx and x["side"] == "BUY" and t0 < x["timestamp"] <= t1]
    return max(px) if px else None


def pnl(idx, px, rate, y, cost_mult=1.0):
    """PnL por acción hasta resolución; cost_mult multiplica la comisión (G4 ×2)."""
    pay = y if idx == 0 else 1 - y
    return pay - px - cost_mult * rate * px * (1 - px)
