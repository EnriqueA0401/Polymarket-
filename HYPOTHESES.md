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

### H007 — H001 restringida a libros con spread bajo (solo forward)
- Fuente: derivada de H001. Sin historial de libro → solo verificable en paper trading.
- Estado: pendiente (baja prioridad) | Gate: — | Variantes: 0

### H009 — Polymarket vs cuotas vivas (forward)
- Fuente: fuentes externas (derivada de H005). Requiere cuotas en vivo simultáneas (p.ej.
  The Odds API, plan gratuito limitado). Solo forward/paper trading. Baja prioridad:
  H005 mostró que PM ya es tan preciso como Pinnacle pre-partido.
- Estado: pendiente | Gate: — | Variantes: 0

### H008 — Seguir a wallets rentables (copy trading con retraso)
- Fuente: flujo de wallets.
- Racional: si existen operadores informados persistentes, sus compras predicen el
  resultado más allá del precio. Quién pierde: la contraparte de esos operadores (takers y
  makers desinformados); el copiador gana solo si la información no se incorpora al precio
  antes de que pueda entrar.
- Protocolo G0 (fijado 2026-10-14, antes de descargar trades):
  - Formación F: mercados de la muestra (h001 ∪ h006r) con closedTime en
    [2025-07-01, 2026-01-01) y volumen ≥ 10k USD (26,689). Trades taker (Data API,
    takerOnly, ≤10,000 más recientes por mercado; truncamiento documentado).
  - PnL realizado por wallet en F: BUY → size·(pago − precio); SELL → size·(precio − pago).
    Anulados pago 0.5. Elegibles: ≥ 20 trades en ≥ 10 eventos distintos.
    Ranking: PnL total / sqrt(nº trades). Top k = 50.
  - Test T: [2026-01-01, 2026-04-12) (antes del holdout). Para cada wallet top: sus trades
    (Data API ?user=) en T; copiar cada BUY en un mercado binario abierto: entrada a precio
    = peor compra taker real del mismo token en (ts+60s, ts+660s]; sin trades → no se copia.
    Una entrada por (wallet, token). Comisión: rate del mercado o 0.07.
  - Predicción falsable: PnL medio por acción > 0 con IC95% cluster (evento) > 0 y ≥ 150
    eventos distintos copiados. Variantes previstas: solo esta (k=50, retraso 60s).
- Estado: activa | Gate: G0 | Variantes: 0

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
- G2 (reports/h006_g2.md): 24h fill 43%, PnL +0.63 c/acción (IC95% −0.43…+1.63);
  7d fill 29%, PnL +0.14 c (IC −2.0…+2.2). Selección adversa fuerte (sin filtrar por
  fill: +2.9 c). Predicción NO cumplida (IC incluye 0) → inconcluso por potencia.
- Réplica pre-registrada (2026-10-14, antes de descargar nada): MISMA regla, solo h=24h,
  eventos de entrenamiento con sha256(event_id) mod 1000 en [150, 450) (disjuntos de la
  muestra usada). Un solo intento. Éxito = IC95% cluster del PnL > 0 en la réplica sola.
  Si falla → H006 rechazada definitivamente.
- Réplica (reports/h006_rep.md): fill 43.6%, PnL +0.27 c (IC −0.54…+1.03). Fallo.
- Estado: RECHAZADA | Gate: falla G2 (y réplica) | Motivo: findings/H006_maker_extremos.md | Variantes: 3

### H005 — Polymarket vs casas de apuestas deportivas
- Fuente: fuentes externas.
- Racional: las casas con mucho volumen agregan mejor información; divergencias
  sistemáticas podrían ser explotables.
- Protocolo G0 (fijado 2026-10-14, antes de cruzar datos):
  - Fuente externa: football-data.co.uk (gratis): resultados y cuotas Pinnacle pre-partido
    (PSH/PSD/PSA, recogidas días antes → conocidas antes de t, sin lookahead) y de cierre
    (PSCH/PSCD/PSCA, SOLO para evaluar CLV, nunca como señal). Ligas: las 5 grandes +
    las demás que cubra football-data.
  - Universo Polymarket: mercados binarios de ganador de partido de fútbol de esas ligas,
    emparejados por fecha y nombres de equipo (tabla de equivalencias versionada en repo;
    los no emparejados se cuentan).
  - t = inicio del partido − 1h. Precio ejecutable = peor precio real pagado por takers del
    lado comprado en (t−1h, t] (Data API); sin trades → no operable.
  - Prob. justa = Pinnacle pre-partido sin margen (normalización proporcional).
  - Señal: comprar en Polymarket el resultado con prob_justa − precio_ejecutable − comisión
    ≥ θ = 0.03 (fijo).
  - Predicción falsable: PnL medio > 0 con IC95% cluster (partido) > 0, y CLV positivo
    frente a Pinnacle cierre. Además (diagnóstico) Brier de Pinnacle pre-partido < Brier
    de Polymarket en t.
  - Quién pierde: aficionados que compran a su equipo en Polymarket por encima del precio
    de un mercado profesional.
  - Limitación: hora exacta de recogida de PSH desconocida (suele ser viernes/martes);
    estrategia real necesitaría cuotas vivas (forward, G7).
  - Aclaración pre-G2: "comprar el resultado" incluye YES (gana X) y NO (no gana X) del
    mercado "Will X win on D?"; prob. justa del NO = 1 − prob. justa del YES.
- G1 (reports/h005_g1.md): 10,889 candidatos, 10,083 emparejados con resolución limpia,
  0 discrepancias PM vs resultado real tras alias/umbral (los ajustes usaron solo la
  coherencia de resolución, nunca precios). endDate = kickoff (mediana 0 h). G1 superado.
- G2 (reports/h005_g2.md): 72 apuestas, PnL −7.3 c (IC −16.0…+2.1); Brier PM 0.1959 vs PS 0.1967.
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H005_polymarket_vs_pinnacle.md | Variantes: 1
