# H018 — Mercados de "mención" (comprar NO) — RECHAZADA en G2

**Veredicto:** no hay sobreprecio significativo del YES en mercados de mención con precios
ejecutables reales 2 h antes del evento.

## Resultados (entrenamiento; holdout NO tocado; reports/h018_g2.md)
- 8,853 mercados; con compra real de NO en (t−2h, t]: 3,501; zona 0.20–0.80: 2,193 (318 eventos).
- PnL +1.04 c/acción (IC95% cluster −2.00…+3.95); sin top-5 eventos −0.60 c.
- Precio medio NO 0.511 vs frecuencia real de NO 0.537 (diferencia ≈ comisión + spread).

Commit 747baca. Variantes: 1. Reproducir: python experiments/h018_g2.py.
