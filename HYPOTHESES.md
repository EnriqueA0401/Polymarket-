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
- Protocolo fijado ANTES de ver datos (2026-10-12):
  - Universo: todos los mercados cerrados con 2 resultados y tokens CLOB, incluidos
    baja liquidez y anulados (anulado = pago 0.5, tratamiento pesimista).
  - Observación: precio CLOB (prices-history) último punto ≤ t, con t = endDate − h,
    h ∈ {24h (principal), 7d}. Solo mercados aún abiertos en t (conocido en t).
  - Estrategia: p ≤ 0.10 → comprar NO; p ≥ 0.90 → comprar YES. Coste: comisión
    vigente del mercado + medio spread pesimista (no hay historial de libro).
  - Split: holdout = closedTime ≥ 2026-04-12 (últimos 6 meses), intocable hasta G3.
  - Muestreo (fijado 2026-10-13, antes de ver precios): el universo elegible tiene
    millones de mercados; se descargan precios de una muestra aleatoria por EVENTO
    (sha256(event_id) mod 1000 < K), K elegido solo por presupuesto (~100k mercados),
    sin mirar resultados. Eventos enteros entran o salen juntos.
  - Clusters = event id. Métricas: gap de calibración por bin, retorno neto por
    operación y anualizado por días hasta cierre.
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
