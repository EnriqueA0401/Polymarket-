"""H034 — Props de esports "Game N"/"Map N" que se anulan a 50-50 si la serie ya está decidida.

Protocolo pre-registrado (HYPOTHESES.md ### H034), 1 variante:
- Universo: eventos de esports "(BO3)/(BO5)/(BO7)" con mercado de serie (moneyline) y props
  "Game N"/"Map N" con N = máximo de partidas y la regla "not played because the series result
  has already been determined ... 50-50" en la descripción.
- t_d = primer trade del mercado de serie con precio ≥ 0.99 (en cualquiera de los dos tokens:
  un trade a ≤ 0.01 es el otro token a ≥ 0.99).
- Prop elegible solo si ningún trade suyo a ≥ 0.99 o ≤ 0.01 ocurre en o antes de t_d.
- Entrada: primer trade taker BUY por token con ts en (t_d + 15 min, t_d + 6 h] y
  precio ≤ 0.5 − comisión(precio) − 0.03. Se toma ese precio y como máximo ese tamaño.
- Pago: resolución real del token (0.5 si anulado).
"""
import re

import numpy as np

from pmq import trades as _trades

HI = 0.99
DELAY_S = 15 * 60
WINDOW_S = 6 * 3600
MARGIN = 0.03
LIMIT = 10000

RULE = re.compile(r"not played because the series(?: result)? has already been determined", re.I)
FIFTY = re.compile(r"50-50", re.I)
BO = re.compile(r"\(BO(\d+)\)", re.I)
GAME_N = re.compile(r"\b(?:Game|Map) (\d+)\b")


def best_of(title):
    """Número máximo de partidas a partir del título del evento ("... (BO3) ..." → 3)."""
    m = BO.search(title or "")
    return int(m.group(1)) if m else None


def game_number(question):
    """N de "Game N"/"Map N" en la pregunta; None si no aparece o aparece más de un N distinto."""
    ns = {int(x) for x in GAME_N.findall(question or "")}
    return ns.pop() if len(ns) == 1 else None


def has_rule(description):
    d = description or ""
    return bool(RULE.search(d) and FIFTY.search(d))


def is_last_game_prop(question, description, title):
    """Prop de la partida N = máximo de una serie impar (Bo3→3, Bo5→5, Bo7→7) con regla 50-50."""
    bo = best_of(title)
    return bool(bo and bo >= 3 and bo % 2 == 1 and game_number(question) == bo and has_rule(description))


def fee(p, rate):
    return rate * p * (1 - p)


def extreme(p):
    return max(p, 1 - p) >= HI


def decided_time(series_trades):
    """t_d: timestamp del primer trade del mercado de serie con max(p, 1−p) ≥ 0.99; None si no hay."""
    ts = [int(t["timestamp"]) for t in series_trades if extreme(float(t["price"]))]
    return min(ts) if ts else None


def prop_ok(prop_trades, t_d):
    """True si ningún trade del prop con precio ≥ 0.99 o ≤ 0.01 ocurre en o antes de t_d."""
    return not any(int(t["timestamp"]) <= t_d and extreme(float(t["price"])) for t in prop_trades)


def max_entry_price(rate, margin=MARGIN):
    """Mayor p con p + rate·p(1−p) ≤ 0.5 − margin (la condición es monótona en p en [0, 0.5])."""
    lo, hi = 0.0, 0.5
    for _ in range(60):
        m = (lo + hi) / 2
        if m + fee(m, rate) <= 0.5 - margin:
            lo = m
        else:
            hi = m
    return lo


def entries(prop_trades, t_d, rate, delay=DELAY_S, window=WINDOW_S, margin=MARGIN):
    """Primer trade taker BUY por outcomeIndex en (t_d+delay, t_d+window] con p ≤ 0.5 − fee − margin.

    Usa solo trades con timestamp ≤ instante de entrada (el orden es por timestamp ascendente)."""
    out = {}
    for t in sorted(prop_trades, key=lambda x: int(x["timestamp"])):
        ts, p = int(t["timestamp"]), float(t["price"])
        if not (t_d + delay < ts <= t_d + window) or str(t["side"]).upper() != "BUY":
            continue
        k = int(t["outcomeIndex"])
        if k in out or p + fee(p, rate) > 0.5 - margin or p <= 0:
            continue
        out[k] = {"outcome": k, "ts": ts, "price": p, "size": float(t["size"])}
    return [out[k] for k in sorted(out)]


def payoff(y, outcome):
    """Pago del token `outcome` dado y = resolución del outcome 0 (1, 0 o 0.5)."""
    return y if outcome == 0 else 1 - y


def pnl(price, rate, pay, fee_mult=1.0, slip=0.0):
    """PnL por acción comprada a price (+slip), con comisión taker fee_mult·rate·q(1−q)."""
    q = min(price + slip, 0.999)
    return pay - q - fee_mult * fee(q, rate)


def cost(price, rate, fee_mult=1.0, slip=0.0):
    q = min(price + slip, 0.999)
    return q + fee_mult * fee(q, rate)


def fetch_full(cid, a, b, cache_dir, fetch=None):
    """Todos los trades taker en [a, b]: parte la ventana si se alcanza el límite de 10,000."""
    fetch = fetch or _trades.fetch
    d = fetch(cid, int(a), int(b), cache_dir)
    if d is None:
        return None
    if len(d) >= LIMIT and b - a > 60:
        mid = (int(a) + int(b)) // 2
        x, y = fetch_full(cid, a, mid, cache_dir, fetch), fetch_full(cid, mid + 1, b, cache_dir, fetch)
        return None if x is None or y is None else x + y
    return d


def portfolio_return(pnl_usd, cap_usd, days):
    """Σpnl / Σ(capital·días) · 365."""
    pnl_usd, cap_usd, days = map(np.asarray, (pnl_usd, cap_usd, days))
    den = (cap_usd * days).sum()
    return float(pnl_usd.sum() / den * 365) if den > 0 else float("nan")
