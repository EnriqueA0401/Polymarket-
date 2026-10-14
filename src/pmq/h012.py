"""H012 — reacción tras saltos de precio. Detección causal (solo datos ≤ t)."""
JUMP, LO, HI = 0.10, 0.05, 0.95


def first_jump(history, end_unix, min_left_s=86400):
    """Primer salto horario |Δp| ≥ JUMP con LO < p < HI y ≥ min_left_s hasta endDate.
    Devuelve (t, dirección +1/−1, p) o None. Usa puntos ordenados por tiempo."""
    h = sorted(history, key=lambda x: x["t"])
    for a, b in zip(h, h[1:]):
        if b["t"] - a["t"] > 2 * 3600:          # hueco: no son consecutivos
            continue
        d = b["p"] - a["p"]
        if abs(d) >= JUMP and LO < b["p"] < HI and end_unix - b["t"] >= min_left_s:
            return b["t"], (1 if d > 0 else -1), b["p"]
    return None
