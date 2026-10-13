# HYPOTHESES

Formato: id | fuente | racional | estado | gate alcanzado | motivo | nº variantes

## Cola (prioridad: probabilidad a priori / coste)

### H002 — Suma de precios en mercados negRisk ≠ 1
- Fuente: inconsistencias internas.
- Racional: en eventos multi-resultado la suma de asks YES < 1 o de bids > 1 permite
  arbitraje; pierde el LP descuidado o el taker impaciente.
- Protocolo G0 (fijado 2026-10-13, antes de ver datos):
  - Universo: eventos abiertos con negRisk=true (resultados mutuamente excluyentes),
    todos los mercados del evento aceptando órdenes. Sin historial de libro → medición
    forward con snapshots periódicos de libros CLOB (G1 = calidad del snapshot).
  - Arbitraje A (largo YES): comprar 1 acción YES de cada resultado barriendo asks;
    coste C_A = Σ precio medio + comisiones taker. Pago = 1 si exactamente uno resuelve YES.
    Si el evento no es exhaustivo (sin "Other"/negRiskAugmented, o placeholders) el pago
    puede ser 0 → se marca y se excluye del arbitraje "seguro".
  - Arbitraje B (largo NO): comprar 1 NO de cada uno de los n resultados; pago n−1.
  - Tamaño: 50 USD por arbitraje (escala del capital < 1.000 USD).
  - Predicción falsable: oportunidades con beneficio neto ≥ 0.5% y rendimiento anualizado
    (por días hasta endDate) ≥ 20% aparecen en ≥ 5 eventos distintos por semana.
    Si no, se rechaza. Si aparecen, G6/G7 deciden (latencia, riesgo de resolución).
  - Quién pierde: takers que compran un resultado sin mirar el resto; LPs con cotizaciones
    obsoletas tras noticias.
- Estado: activa | Gate: G0 | Variantes: 0

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

### H006 — Market making en extremos (maker, sin comisión, con rebate)
- Fuente: microestructura / derivada de H001.
- Racional: el sesgo favorito-longshot queda dentro del spread; quien lo captura es el maker.
  Pierden los takers compradores de longshots. Riesgo: selección adversa al acercarse
  la resolución. Requiere datos de trades (Data API) para modelar fills sin optimismo.
- Estado: pendiente | Gate: — | Variantes: 0

### H007 — H001 restringida a libros con spread bajo (solo forward)
- Fuente: derivada de H001. Sin historial de libro → solo verificable en paper trading.
- Estado: pendiente (baja prioridad) | Gate: — | Variantes: 0

## Cerradas

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
    sin mirar resultados. Fijado tras contar el universo: K_train=150, K_holdout=20
    (entrenamiento 425k mercados, holdout 2.24M; ver reports/h001_g1_universe.md). Eventos enteros entran o salen juntos.
  - Clusters = event id. Métricas: gap de calibración por bin, retorno neto por
    operación y anualizado por días hasta cierre.
- Estado: RECHAZADA | Gate: falla G2 | Motivo: borde bruto ≈1 c/acción < coste real ≈2 c
  (findings/H001_favorito_longshot.md) | Variantes: 3

