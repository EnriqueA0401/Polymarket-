# HYPOTHESES

Formato: id | fuente | racional | estado | gate alcanzado | motivo | nº variantes

## Cola (prioridad: probabilidad a priori / coste)

### H001 — Sesgo favorito-longshot
- Fuente: sesgos de calibración.
- Racional: apostadores minoristas sobrepagan resultados improbables (lotería,
  atención, entretenimiento). Pierden los compradores de longshots; gana quien vende
  longshots (compra NO barato-caro) o compra favoritos.
- Predicción falsable (G0): en mercados binarios resueltos, la frecuencia empírica de
  YES para precios ≤0.10 (medidos a horizonte fijo antes del cierre) es inferior al
  precio medio, y para ≥0.90 es superior; la diferencia supera el coste de ejecución
  (spread+comisión) con IC95% por clusters de evento > 0.
- Estado: activa | Gate: G0 | Variantes: 0

### H002 — Suma de precios en mercados negRisk ≠ 1
- Fuente: inconsistencias internas.
- Racional: en eventos multi-resultado la suma de asks YES < 1 o de bids > 1 permite
  arbitraje; pierde el LP descuidado o el taker impaciente.
- Estado: pendiente | Gate: — | Variantes: 0

### H003 — Sobreprecio de "Yes"
- Fuente: sesgos de calibración.
- Racional: sesgo de afirmación; el minorista compra la opción "Yes". Pierde quien
  compra YES por defecto.
- Estado: pendiente | Gate: — | Variantes: 0

### H004 — Deriva cerca de la resolución (decaimiento temporal)
- Fuente: dinámica temporal.
- Racional: mercados casi decididos cotizan con descuento por coste de capital y
  riesgo de resolución; ¿es el descuento mayor que el riesgo real?
- Estado: pendiente | Gate: — | Variantes: 0

### H005 — Polymarket vs casas de apuestas deportivas
- Fuente: fuentes externas.
- Racional: las casas con mucho volumen agregan mejor información; divergencias
  sistemáticas podrían ser explotables.
- Estado: pendiente | Gate: — | Variantes: 0

## Cerradas
(ninguna)
