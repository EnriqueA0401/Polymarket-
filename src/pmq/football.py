"""H005 — datos de football-data.co.uk y emparejamiento con mercados de Polymarket.

Mercados PM: "Will <equipo> win on <YYYY-MM-DD>?" (binarios). Se emparejan con el partido de
football-data de la liga correspondiente (por series) con fecha ±1 día y máxima similitud
de nombre; se exige score ≥ MIN_SCORE y margen ≥ MIN_MARGIN frente al segundo candidato.
"""
import glob, os, re, unicodedata
from difflib import SequenceMatcher
import numpy as np
import pandas as pd

from pmq.universe import DATA

SERIES_TO_LEAGUE = {
    "premier-league-2025": "E0", "epl": "E0", "efl-championship": "E1",
    "la-liga-2025": "SP1", "la-liga-2": "SP2", "bundesliga-2025": "D1", "bundesliga-2": "D2",
    "serie-a-2025": "I1", "serie-b": "I2", "ligue-1-2025": "F1", "ligue-2": "F2",
    "ere-2025": "N1", "primeira-liga": "P1", "tur-2025": "T1", "scottish-premiership": "SC0",
    "bel1-games": "B1",
}
STOP = {"fc", "cf", "afc", "sc", "ac", "as", "ss", "us", "club", "de", "calcio", "sv", "vfb", "vfl",
        "tsg", "rc", "rcd", "ud", "cd", "sd", "ca", "the", "fk", "sk", "bk", "if", "kv", "krc", "rsc",
        "sporting", "clube", "football", "futebol", "1", "04", "05", "1899", "1846", "1907", "1909", "1913"}
MIN_SCORE, MIN_MARGIN = 0.75, 0.10
# Abreviaturas de football-data → nombre completo (tras norm()). Versionado: añadir aquí.
ALIASES = {
    "paris sg": "paris saint germain", "man city": "manchester city", "man united": "manchester united",
    "sheffield weds": "sheffield wednesday", "espanol": "espanyol", "sp gijon": "real sporting gijon",
    "nott m forest": "nottingham forest", "wolves": "wolverhampton wanderers", "ein frankfurt": "eintracht frankfurt",
    "m gladbach": "borussia monchengladbach", "koln": "koln", "qpr": "queens park rangers",
    "west brom": "west bromwich albion", "ath madrid": "atletico madrid", "ath bilbao": "athletic bilbao",
    "sociedad": "real sociedad", "betis": "real betis", "inter": "internazionale inter", "milan": "milan",
    "dortmund": "borussia dortmund", "leverkusen": "bayer leverkusen", "bayern munich": "bayern munchen",
    "st etienne": "saint etienne", "psv eindhoven": "psv", "sp lisbon": "sporting lisbon cp",
    "dundee": "dundee", "dundee united": "dundee united", "santander": "real racing club santander",
}
# Tokens que distinguen clubes de la misma ciudad: la contención no vale si el nombre más
# largo añade uno de estos (Paris FC ⊄ Paris Saint-Germain, Dundee ⊄ Dundee United).
DISTINCT = {"united", "wednesday", "saint", "germain", "athletic", "atletico", "real", "sporting", "rangers",
            "city", "county", "albion", "wanderers", "rovers", "hotspur", "villa", "forest"}
Q_RE = re.compile(r"^Will (.+) win on (\d{4}-\d{2}-\d{2})\?$")


def norm(name):
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [t for t in s.split() if t not in STOP]
    out = " ".join(toks) or s.strip()
    return ALIASES.get(out, out)


GENERIC = {"real", "wanderers", "rovers", "albion", "town", "county", "hotspur"}


def core(n):
    """Quita palabras genéricas compartidas por muchos clubes (Real Oviedo ≠ Real Sociedad)."""
    t = [x for x in n.split() if x not in GENERIC]
    return " ".join(t) if t else n


def sim(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    ca, cb = core(a), core(b)
    r = SequenceMatcher(None, ca, cb).ratio()
    ta, tb = set(a.split()), set(b.split())
    if ta and tb and (ta <= tb or tb <= ta):  # un nombre contenido en el otro ("coventry" ⊂ "coventry city")
        extra = (ta ^ tb)
        if not (extra & DISTINCT) or extra <= {"city"}:
            r = max(r, 0.85)
    return r


def load_fd():
    rows = []
    for f in sorted(glob.glob(os.path.join(DATA, "football", "*.csv"))):
        season, league = os.path.basename(f)[:-4].split("_", 1)
        try:
            d = pd.read_csv(f, encoding="latin-1", on_bad_lines="skip")
        except (pd.errors.EmptyDataError, UnicodeDecodeError):
            continue
        if "HomeTeam" not in d:
            continue
        d["league"], d["season"] = league, season
        rows.append(d)
    fd = pd.concat(rows, ignore_index=True)
    fd["date"] = pd.to_datetime(fd.Date, dayfirst=True, errors="coerce", format="mixed")
    t = fd.get("Time", pd.Series("15:00", index=fd.index)).fillna("15:00")
    ko = pd.to_datetime(fd.date.dt.strftime("%Y-%m-%d") + " " + t, errors="coerce")
    fd["kickoff"] = ko.dt.tz_localize("Europe/London", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    return fd.dropna(subset=["date", "kickoff", "FTR"])


def match_markets(pm, fd):
    """pm: DataFrame con id, question, series. Devuelve pm con columnas del partido emparejado."""
    fd = fd.assign(d=fd.date.dt.normalize())
    by_key = {k: g for k, g in fd.groupby(["league", "d"])}
    out = []
    for r in pm.itertuples():
        m = Q_RE.match(r.question or "")
        lg = SERIES_TO_LEAGUE.get(r.series)
        if not m or not lg:
            continue
        team, day = m.group(1), pd.Timestamp(m.group(2))
        cands = pd.concat([by_key[(lg, day + pd.Timedelta(days=k))] for k in (-1, 0, 1)
                           if (lg, day + pd.Timedelta(days=k)) in by_key] or [pd.DataFrame()])
        if cands.empty:
            out.append({"id": r.id, "status": "sin_partido"}); continue
        sc = []
        for c in cands.itertuples():
            sh, sa = sim(team, c.HomeTeam), sim(team, c.AwayTeam)
            sc.append((max(sh, sa), "H" if sh >= sa else "A", c.Index))
        sc.sort(reverse=True)
        best = sc[0]; second = sc[1][0] if len(sc) > 1 else 0.0
        if best[0] < MIN_SCORE or best[0] - second < MIN_MARGIN:
            out.append({"id": r.id, "status": "ambiguo", "score": best[0]}); continue
        c = fd.loc[best[2]]
        out.append({"id": r.id, "status": "ok", "score": best[0], "team": team, "side": best[1],
                    "fd_home": c.HomeTeam, "fd_away": c.AwayTeam, "league": lg, "kickoff": c.kickoff,
                    "FTR": c.FTR, "fd_idx": best[2]})
    return pd.DataFrame(out)


def consistent(ok):
    """Cada equipo PM debe mapear siempre al mismo nombre de football-data (el modal).
    Se descartan los emparejamientos que se desvían (errores puntuales de fecha/competición)."""
    fdname = ok.apply(lambda r: r.fd_home if r.side == "H" else r.fd_away, axis=1)
    modal = fdname.groupby(ok.team).agg(lambda s: s.value_counts().index[0])
    return ok[fdname.values == modal.reindex(ok.team).values]


def fair_prob(row, prefix="PS"):
    """Prob. sin margen (normalización proporcional) de que gane el lado `side`."""
    o = [row.get(f"{prefix}{k}") for k in ("H", "D", "A")]
    if any(pd.isna(x) or x <= 1 for x in o):
        return np.nan
    inv = np.array([1 / x for x in o])
    p = inv / inv.sum()
    return p[0] if row["side"] == "H" else p[2]
