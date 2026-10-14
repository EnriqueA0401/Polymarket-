# H034 — Props de esports "Game N" que se anulan a 50-50 — RECHAZADA en G2

**Veredicto:** con información disponible en t no se puede identificar de forma fiable que la
partida N no se jugará; lo que se compra barato suelen ser los perdedores de esa partida.

## Resultados (entrenamiento; holdout NO tocado; reports/h034_g2.md)
- 5,084 props con regla 50-50 (1,743 series) → 4,805 con t_d → 4,729 sin trades extremos →
  89 entradas en 65 series (regla presente solo desde marzo 2026: ~5 semanas de historia).
- Tasa de anulación en las entradas 0.213 (exigido ≥ 0.90; 0.62 en todos los elegibles).
- PnL −1.9 c/acción (IC95% −6.9…+3.8); costes×2 −3.5 c; sin top-5 −5.9 c (IC −10.0…−1.3).
- Tamaño mediano ejecutable ≈ 1 USD; capacidad ≈ 243 USD/mes.

## Causa
El mercado de la serie alcanza 0.99 al terminar una partida N que SÍ se jugó; 69/89 entradas
fueron tokens perdedores de esa partida.

Implementación: subagente; 119 tests. Commit 551683e. Variantes: 1.
