# H013 — Recompensas de liquidez — DESCARTADA (decisión del usuario)

**Veredicto:** descartada el 2026-10-14 por indicación del usuario, que ya la probó con
operativa real y no obtuvo buenos resultados. Esa evidencia es externa al repo (no
reproducible aquí); se registra como tal.

## Lo medido antes de descartarla
- Etapa 1 (snapshot vivo): 13,876 mercados con recompensas; rendimientos esperados
  "demasiado buenos" (cuota 100% en libros vacíos) → tratados como sospechosos.
- Etapa 2a (entrenamiento, 300 mercados): selección adversa mediana ~0 USD/día vs
  recompensa máxima mediana 10 USD/día (supone cuota 100%, no realista).
- Pagos reales existen (Data API /activity?type=REWARD), pero se concentran en makers grandes.
- Etapa 2b (paper trading) detenida tras < 1 h; sin resultados.

## Lectura
La brecha entre recompensa nominal y resultado real sugiere factores no modelados
(cuota real, reglas de puntuación/midpoint ajustado, selección adversa en vivo, competencia
intermitente). No se invierte más tiempo en esta familia.

Commit 519a1f5. Variantes: 1.
