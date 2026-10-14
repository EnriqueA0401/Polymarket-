# H020 — Deriva de la primera hora en mercados nuevos — RECHAZADA en G2

**Veredicto:** ni seguir ni revertir la deriva de la primera hora es rentable; en libros
nuevos y finos comprar al peor precio cuesta demasiado. Muestra además insuficiente.

## Resultados (entrenamiento; holdout NO tocado; reports/h020_g2.md)
- 7,783 mercados muestreados → 7,597 con primer trade → 4,797 con trade YES en la 1ª hora →
  564 con trades en [a0+50m, a0+60m] → 128 señales (mediana: 2 trades taker en 2 h).
- A momentum: 90 ops (83 eventos), PnL −8.6 c (IC −17.0…−0.1); costes×2 −13.4 c.
- B reversión: 80 ops (75 eventos), PnL −18.0 c (IC −27.4…−7.9); costes×2 −23.9 c.
- Holm: ninguna significativa a favor. Peor YES + peor NO en la ventana ≈ 1.25 (media).

## Sustituciones (ver informe)
Primer precio = primer trade YES de la 1ª hora; precio actual = VWAP 50–60 min; costes×2 =
comisión×2 + deslizamiento extra. Implementación: subagente; 72 tests en verde.

Commit 642bc01. Variantes: 2.
