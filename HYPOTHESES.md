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
- Protocolo G0 (fijado 2026-10-14, antes de ver resultados):
  - Universo: muestra de H001 (misma regla), entrenamiento. Señal en t = end − h con
    p_t (prices-history, solo para decidir): 0.02 < p_t ≤ 0.10 → vender YES (orden límite
    de compra de NO a q = 1 − (p_t + 0.01)); p_t ≥ 0.90 y < 0.98 → comprar YES a p_t − 0.01.
  - Fill pesimista con trades taker reales en (t, t+24h]: solo si algún taker cruzó
    ESTRICTAMENTE nuestro nivel (lado longshot: taker compra YES a precio > p_t+0.01, o
    vende NO a < q; lado favorito: taker vende YES a < p_t−0.01, o compra NO a >
    1−(p_t−0.01)). Fill al precio de nuestra orden, una vez. Sin fill → no hay posición.
  - PnL por acción: pago − precio; makers sin comisión; rebates NO contados. Capital
    bloqueado hasta cierre → anualizar.
  - Variantes: h=24h (principal), h=7d.
  - Predicción falsable: fill rate ≥ 20% y PnL medio por fill > 0 con IC95% cluster > 0.
  - Quién pierde: takers que compran longshots / venden favoritos con prisa. Riesgo: los
    fills llegan justo cuando hay información (selección adversa) → el test lo mide.
- Estado: activa | Gate: G0 | Variantes: 0

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

### H003 — Sobreprecio de "Yes"
- Fuente: sesgos de calibración.
- Racional: sesgo de afirmación; el minorista compra la opción "Yes". Pierde quien
  compra YES por defecto.
- Protocolo G0 (fijado 2026-10-13). CONTAMINACIÓN DECLARADA: al revisar H001 vi la
  calibración agregada en entrenamiento (bins 0.4–0.6: precio > frecuencia en 3–10 pts),
  sin filtrar por tipo de resultado. Por eso el veredicto depende del holdout (G3).
  - Universo: muestra de H001 (misma regla), mercados con resultados exactamente
    ["Yes","No"]. Control: mercados con otros nombres (equipos, Over/Under): si el primer
    resultado está igual de sobrevalorado, no es sesgo de "Yes" sino artefacto.
  - Filtro de negociación (anti-artefacto 0.5 inicial): ≥ 2 precios distintos en las 24h
    previas a t. Fijado ahora, antes de ver el resultado filtrado.
  - Señal: 0.20 ≤ p ≤ 0.80 en t = end − 24h → comprar NO. Coste 0.02/acción + comisión.
  - Predicción falsable: en Yes/No, frecuencia de YES < precio medio − 0.03 y retorno neto
    medio > 0 con IC95% cluster > 0; en el control, diferencia significativamente menor.
  - Variantes previstas: h=24h (principal), h=7d.
- G2 (reports/h003_g2.md): Yes/No 24h ret +2.2% (IC −0.0%…4.4%); 7d +8.7% (IC 6.3…11.2%);
  control 7d +3.7%. PERO coste vivo en zona 0.2–0.8 (reports/h003_live_costs.md): spread
  mediano 0.77, coste mediano 0.39/acción → precios históricos probablemente no ejecutables.
  Pendiente: verificar con trades reales (Data API) antes de seguir.
- Ejecutabilidad (reports/h003_exec.md): con peor precio real de compra de NO, 24h −11.0%,
  7d −5.9%. Borde = artefacto de precios no ejecutables.
- Estado: RECHAZADA | Gate: falla G1/G2 (precios no ejecutables) | Motivo: findings/H003_sobreprecio_yes.md | Variantes: 3
