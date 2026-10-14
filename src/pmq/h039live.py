"""H039 forward — snapshots de libros Kalshi ↔ Polymarket para partidos abiertos emparejados (NFL/NBA/MLB).
Cada snapshot: partidos con gameStartTime futuro emparejados con la lógica de H023; para cada dirección
e ∈ {0, 1} y tamaño S: coste ejecutable de comprar S contratos de exposición "gana team e" en Kalshi (el más
barato entre YES del mercado de e y NO del mercado del rival, barriendo el libro, comisión taker por nivel)
+ S acciones del token 1 − e en PM (barriendo asks, comisión del mercado). Beneficio por par = 1 − coste/S.
Uso: PYTHONPATH=src python -m pmq.h039live [--loop MINUTOS] → data/h039/live.csv"""
import argparse, json, os, time
import numpy as np
import pandas as pd
import requests

from pmq import h023 as H
from pmq import h039 as A
from pmq.h002 import books, buy_cost, fee_rate
from pmq.universe import DATA

OUT = os.path.join(DATA, "h039")
SIZES = (10, 100)
GAMMA = "https://gamma-api.polymarket.com"


def _gget(path, params, tries=5):
    for i in range(tries):
        try:
            r = requests.get(GAMMA + path, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(2 ** i)
    raise RuntimeError(f"Gamma {path} {params} falló")


def pm_open(now):
    """Mercados moneyline abiertos de las series PM de H023 con inicio futuro."""
    rows = []
    for lg, (_, slugs) in H.LEAGUES.items():
        for slug in slugs:
            for s in _gget("/series", {"slug": slug}):
                off = 0
                while True:
                    ev = _gget("/events", {"series_id": s["id"], "closed": "false", "limit": 500, "offset": off})
                    for e in ev:
                        for m in e.get("markets") or []:
                            q = m.get("question") or ""
                            if m.get("sportsMarketType") not in (None, "moneyline") or ":" in q or " vs" not in q:
                                continue
                            if m.get("closed") or not m.get("acceptingOrders") or not m.get("gameStartTime"):
                                continue
                            outs, toks = json.loads(m.get("outcomes") or "[]"), json.loads(m.get("clobTokenIds") or "[]")
                            gs = pd.to_datetime(m["gameStartTime"], utc=True, errors="coerce", format="mixed")
                            if len(outs) != 2 or len(toks) != 2 or pd.isna(gs) or gs <= now:
                                continue
                            rows.append({"id": int(m["id"]), "league": lg, "question": q, "o0": outs[0], "o1": outs[1],
                                         "description": m.get("description") or "", "game_start": gs,
                                         "tok0": toks[0], "tok1": toks[1], "rate": fee_rate(m)})
                    if len(ev) < 500:
                        break
                    off += 500
    df = pd.DataFrame(rows)
    return df.drop_duplicates("id") if len(df) else df


def k_open():
    """Mercados abiertos de Kalshi (ganador del partido) → eventos por liga (formato de H023.k_events)."""
    out = []
    for lg, (series, _) in H.LEAGUES.items():
        mk, cur = [], None
        while True:
            q = {"series_ticker": series, "status": "open", "limit": 1000}
            if cur:
                q["cursor"] = cur
            d = H.k_get("/markets", q)
            mk += d.get("markets", [])
            cur = d.get("cursor")
            if not cur or not d.get("markets"):
                break
        out += H.k_events(mk, lg)
    return out


def k_book(ticker):
    d = H.k_get(f"/markets/{ticker}/orderbook", {})
    return (d or {}).get("orderbook_fp") or {}


def snapshot():
    now = pd.Timestamp.now(tz="UTC")
    pm = pm_open(now)
    kev = k_open()
    if not len(pm) or not kev:
        print(f"{now:%Y-%m-%d %H:%M} sin mercados (pm={len(pm)}, kalshi={len(kev)})", flush=True)
        return pd.DataFrame()
    m = H.match(pm, kev)
    ok = m[m.status == "ok"].merge(pm, on=["id", "league"])
    ok = ok[~ok.k_event.duplicated(keep=False)]                       # un evento Kalshi ↔ un mercado PM
    kmap = {e["event_ticker"]: e for e in kev}
    bk = books([t for r in ok.itertuples() for t in (r.tok0, r.tok1)])
    rows = []
    for r in ok.itertuples():
        e_ = kmap[r.k_event]
        tick = {0: e_["mk"][r.team0]["ticker"], 1: e_["mk"][r.team1]["ticker"]}
        kb = {i: k_book(t) for i, t in tick.items()}
        for e in (0, 1):
            yes_e = A.k_asks(kb[e], "yes")            # YES del mercado del equipo e
            no_o = A.k_asks(kb[1 - e], "no")          # NO del mercado del rival
            pm_book = bk.get(r.tok1 if e == 0 else r.tok0)
            for S in SIZES:
                c_yes, c_no = A.k_buy_cost(yes_e, S), A.k_buy_cost(no_o, S)
                k_cost = np.nanmin([c_yes, c_no]) if not (np.isnan(c_yes) and np.isnan(c_no)) else np.nan
                pm_cost = buy_cost(pm_book, S, r.rate)
                tot = k_cost + pm_cost
                rows.append({
                    "ts": now.isoformat(), "league": r.league, "pm_id": r.id, "question": r.question,
                    "k_event": r.k_event, "game_start": r.game_start.isoformat(),
                    "h_to_start": (r.game_start - now).total_seconds() / 3600, "e": e,
                    "team_k": r.team0 if e == 0 else r.team1, "size": S,
                    "k_instr": "" if np.isnan(k_cost) else ("yes" if c_yes == k_cost else "no_rival"),
                    "k_best_yes": yes_e[0][0] if yes_e else np.nan, "k_best_no_rival": no_o[0][0] if no_o else np.nan,
                    "pm_best_ask": min((float(a["price"]) for a in (pm_book or {}).get("asks") or []), default=np.nan),
                    "pm_rate": r.rate, "k_cost": k_cost, "pm_cost": pm_cost, "cost_per_pair": tot / S,
                    "profit_per_pair": 1 - tot / S, "opp": bool(tot / S < A.THRESH) if not np.isnan(tot) else False})
    os.makedirs(OUT, exist_ok=True)
    df = pd.DataFrame(rows)
    p = os.path.join(OUT, "live.csv")
    if len(df):
        df.to_csv(p, mode="a", header=not os.path.exists(p), index=False)
    n_opp = int(df.opp.sum()) if len(df) else 0
    best = df.profit_per_pair.max() if len(df) else np.nan
    print(f"{now:%Y-%m-%d %H:%M} pm={len(pm)} kalshi_eventos={len(kev)} emparejados={len(ok)} filas={len(df)} "
          f"opp={n_opp} mejor_beneficio={best:.4f}", flush=True)
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--loop", type=float, default=0); a = ap.parse_args()
    while True:
        try:
            snapshot()
        except Exception as e:
            print("ERROR", repr(e)[:200], flush=True)
        if not a.loop:
            break
        time.sleep(a.loop * 60)
