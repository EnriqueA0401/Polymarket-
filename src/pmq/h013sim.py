"""H013 etapa 2a: simulación de maker a mid ± v/2 con fills pesimistas por trades reales."""


def simulate(mids, trades, v, size, y):
    """mids: lista ordenada (t_minuto, mid) con mid conocido en t; trades: taker con
    outcomeIndex/side/price/timestamp. Cotiza en cada minuto [t, t+60). Fill (una vez por
    lado y minuto) solo si un trade cruza ESTRICTAMENTE el nivel. Devuelve (pnl, n_bid, n_ask)."""
    tr = sorted(trades or [], key=lambda x: x["timestamp"])
    pnl, nb, na, j = 0.0, 0, 0, 0
    for t, mid in mids:
        bid, ask = mid - v / 2, mid + v / 2
        while j < len(tr) and tr[j]["timestamp"] <= t:
            j += 1
        k, hb, ha = j, False, False
        while k < len(tr) and tr[k]["timestamp"] < t + 60:
            x = tr[k]; px = float(x["price"]); i, s = x["outcomeIndex"], x["side"]
            if not hb and ((i == 0 and s == "SELL" and px < bid) or (i == 1 and s == "BUY" and px > 1 - bid)):
                hb = True
            if not ha and ((i == 0 and s == "BUY" and px > ask) or (i == 1 and s == "SELL" and px < 1 - ask)):
                ha = True
            k += 1
        if hb:
            pnl += size * (y - bid); nb += 1
        if ha:
            pnl += size * (ask - y); na += 1
    return pnl, nb, na
