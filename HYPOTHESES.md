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

### H007 — H001 restringida a libros con spread bajo (solo forward)
- Fuente: derivada de H001. Sin historial de libro → solo verificable en paper trading.
- Estado: pendiente (baja prioridad) | Gate: — | Variantes: 0

### H009 — Polymarket vs cuotas vivas (forward)
- Fuente: fuentes externas (derivada de H005). Requiere cuotas en vivo simultáneas (p.ej.
  The Odds API, plan gratuito limitado). Solo forward/paper trading. Baja prioridad:
  H005 mostró que PM ya es tan preciso como Pinnacle pre-partido.
- Estado: pendiente | Gate: — | Variantes: 0

### H010 — Incoherencias entre fechas ("¿X antes de D1?" vs "¿X antes de D2?")
- Fuente: inconsistencias internas. En un evento con varias fechas límite, P(antes de D1)
  ≤ P(antes de D2) si D1 < D2. Violaciones ejecutables (ask D2 < bid D1 tras costes) son
  arbitraje. Medición forward con libros vivos (como H002) y retro con trades.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Universo: eventos abiertos NO negRisk con ≥ 2 mercados binarios aceptando órdenes,
    cuyas preguntas contienen " by " y difieren en endDate (escalera de fechas límite).
  - Para cada par D1 < D2 del mismo evento: comprar NO(D1) + YES(D2) barriendo asks para
    50 acciones; pago ≥ 1 en todos los escenarios (2 si ocurre entre D1 y D2).
    Retorno = (50 − coste)/coste, coste con comisiones taker; anualizado hasta endDate(D2).
  - Riesgo declarado: reglas no anidadas (fuentes/definiciones distintas por fecha);
    cada oportunidad positiva se revisa manualmente leyendo las reglas antes de contarla.
  - Predicción falsable: ≥ 5 eventos distintos por semana con retorno ≥ 0.5% y anualizado
    ≥ 20%. Si no, se rechaza. Medición: snapshots horarios durante 7 días.
  - Quién pierde: quien compra la fecha corta (o vende la larga) sin mirar la escalera.
- Estado: activa | Gate: G0 | Variantes: 0

### H019 — Ventana de propuesta UMA (comprar el lado propuesto antes del settle)
- Fuente: subagente; generaliza H015. Requiere eventos ProposePrice on-chain (Polygon).
  Prior rebajado: H015 mostró que tras el evento el precio ya está ≥0.995 casi siempre.
  Estado: pendiente (baja prioridad) | Variantes: 0

### H021 — Arbitraje combinatorio (candidato vs partido, estado vs nacional, moneyline vs spread)
- Fuente: subagente (arXiv 2508.03474). Coste alto; ventanas de segundos. Estado: pendiente | Variantes: 0

### H022 — Macro (PIB, IPC, Fed) vs nowcasts oficiales (GDPNow, Cleveland Fed)
- Fuente: subagente. Conteo en entrenamiento: PIB 25 eventos, Fed 84, IPC ~60 publicaciones
  mensuales independientes, paro 52 → imposible alcanzar 150 independientes (G4).
- Estado: DESCARTADA antes de probar (G4 estructuralmente imposible) | Variantes: 0

### H026 — Carry en NO a 90 días solo en mercados NO negRisk (forward)
- Fuente: subgrupo post hoc del red team de H024 (+3.6 c). Holdout ya consumido para esta
  familia → solo validable en paper trading forward (G7) con rentabilidad de cartera.
- Protocolo G7 forward (fijado 2026-10-14, antes de registrar ninguna señal):
  - Diario: mercados binarios ABIERTOS, NO negRisk, start ≤ end − 120 d, con endDate entre
    80 y 100 días vista, aceptando órdenes, mid YES (libro) en [0.02, 0.10].
  - Entrada simulada: comprar 50 acciones de NO barriendo asks del libro vivo (+comisión);
    una sola entrada por mercado (la primera señal). Se guarda libro y precio.
  - Seguimiento: resolución real (Gamma). Métrica: rentabilidad de CARTERA
    Σpnl / Σ(capital·días)·365 sobre mercados resueltos; censura: solo eventos totalmente
    resueltos.
  - Éxito: ≥ 50 mercados resueltos con PnL > 0 (IC95% bootstrap por evento > 0) y
    rentabilidad de cartera > 6%/año. Horizonte: ~3–4 meses (resolución a ~90 d).
- Estado: activa (forward, registro diario) | Gate: G7 | Variantes: 0

### H029–H031 — Solo forward (menos de 150 eventos en entrenamiento)
- H029 TSA pasajeros diarios (modelo estacional); H030 Netflix top 10 semanal con rankings
  diarios; H031 taquilla de estreno con preestrenos.
- Estado: pendientes (forward cuando haya capacidad) | Variantes: 0

### H033 — Combinatorio: P(gana presidencia 2028) ≤ P(gana nominación de su partido)
- Fuente: H021 (arbitraje combinatorio), caso concreto y verificable.
- Racional: para cada candidato, comprar NO(presidencia) + YES(nominación) paga ≥ 1 salvo que
  gane la presidencia sin la nominación (independiente/sustitución: riesgo declarado, raro).
  Si el coste < 1 tras comisiones hay arbitraje casi puro. Pierden quienes compran el YES de
  presidencia de un candidato sin mirar su nominación.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Eventos 31552 (presidencia 2028) y 30829/31875 (nominaciones D/R); emparejar por nombre.
  - Snapshot cada 6 h: coste de 50 acciones de cada pierna barriendo asks + comisión.
  - Retorno = (50 − coste)/coste; anualizado de cartera hasta la elección (nov 2028).
  - Éxito (forward, 4 semanas): ≥ 5 candidatos distintos con retorno ≥ 1% y anualizado
    ≥ 6% en algún snapshot, confirmados leyendo las reglas. Si no → rechazar.
- Estado: activa (forward) | Gate: G0 | Variantes: 0

### H036 — Conversión NO→YES instantánea en negRisk (re-especificación de H002-B)
- Fuente: subagente. Si Σ bids YES de los otros resultados > precio de NO de uno + costes,
  comprar NO, convertir (adapter) y vender YES al instante: sin capital bloqueado.
- Protocolo: sobre los libros crudos ya guardados de H002 (data/h002/snap_*), calcular para
  cada evento y resultado i: ingreso = Σ_{j≠i} (venta de 50 YES_j barriendo bids) − coste de
  50 NO_i barriendo asks − comisiones. Predicción: ≥ 5 eventos/semana con beneficio ≥ 1 USD
  por 50 acciones.
  - ENMIENDA (antes de ver datos): los crudos de H002 solo contienen eventos con algún retorno
    > 0 (subconjunto sesgado) → medición FORWARD integrada en los snapshots de H002 desde
    2026-10-14 (data/h002/opps_conv.csv), solo eventos no aumentados con todos los mercados
    activos. Evaluar junto a H002 (~2026-10-21).
- Estado: activa | Gate: G0 | Variantes: 0

### H037 — Monotonía en escaleras de strikes ("above/reach K", mismo endDate)
- Fuente: subagente. YES(K bajo) + NO(K alto) < 1 → arbitraje (paga ≥ 1 en todo escenario
  para "above/reach"; para "below/dip" se invierte el orden). Prior 5%.
- Protocolo G0 forward (fijado 2026-10-14, antes de ver datos):
  - Eventos abiertos NO negRisk; mercados del mismo evento con el mismo endDate cuya pregunta
    contiene "above/reach/hit" (o "below/dip/fall") y un importe $K; misma plantilla salvo K.
  - Para cada par K1 < K2: coste de 50 YES(K1) + 50 NO(K2) (above/reach) o 50 YES(K2) + 50
    NO(K1) (below/dip) barriendo asks + comisión. Retorno = (50 − coste)/coste.
  - Snapshots cada hora durante 7 días. Éxito: ≥ 5 eventos distintos/semana con retorno ≥ 0.5%.
- Estado: activa (forward) | Gate: G0 | Variantes: 0

### H038 [BIN] — Calibración en Kalshi con precios ejecutables (favorito-longshot)
- Fuente: ampliación a opciones binarias; literatura (CEPR/VoxEU: sesgo favorito-longshot en
  Kalshi). Racional: base minorista mayor y comisión distinta a PM → el sesgo podría superar
  el coste allí. Pierden compradores de longshots.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos de Kalshi):
  - Universo: mercados binarios liquidados de Kalshi (todas las series con historial
    público), entrenamiento = liquidados < 2026-04-12; holdout = posteriores (intocable).
    Muestra aleatoria por evento si hay demasiados (regla fijada por presupuesto).
  - t = cierre programado − 24 h. Precio ejecutable = peor compra taker real (trades públicos)
    del lado elegido en (t−1 h, t]. Comisión Kalshi: ceil(0.07·C·P·(1−P)) en céntimos por orden
    (taker); verificar tabla de comisiones vigente por serie.
  - Señal: P ≤ 0.10 → comprar NO; P ≥ 0.90 → comprar YES (como H001).
  - Predicción: PnL > 0 con IC95% cluster (evento) > 0; costes×2 > 0. Variantes: 1.
- Estado: activa | Gate: G0 | Variantes: 0

### H039 [BIN] — Arbitraje entre plataformas Kalshi ↔ Polymarket (mismo evento)
- Fuente: ampliación; emparejamiento ya hecho en H023 (deportes, 3,962 partidos).
- Racional: si en el mismo instante YES en una plataforma + NO en la otra cuestan < 1 tras
  comisiones, el pago es 1 seguro (salvo diferencias de reglas). Pierde el lado lento.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Histórico (entrenamiento): para cada partido emparejado, ventanas de 1 min antes del inicio
    con trades taker de compra en ambas plataformas: coste = peor compra YES_K + peor compra
    NO_PM (y la combinación inversa) en el mismo minuto + comisiones de ambas. Oportunidad si
    coste < 0.99.
  - Forward: snapshots de libros de ambas plataformas cada 30 min durante 7 días.
  - Predicción: ≥ 150 partidos con oportunidad y beneficio medio ≥ 1 c por par tras comisiones,
    reglas de resolución verificadas idénticas. Variantes: 1.
- Resultado G2 (2026-10-15, reports/h039_g2.md): 422 partidos con oportunidad, 1ª oportunidad
  +5.75 c (+5.27 c sin top-5); ×2 costes: 191 partidos. PERO reglas NO idénticas (aplazado > 48 h
  o cancelado: Kalshi paga 'precio justo', PM espera/50-50; casos reales pagaron 0.56–0.62) y 3
  partidos resueltos distinto. Tamaño mediano 15 contratos; capacidad ~1,315 USD/año sin top-5;
  44% con firma de bot que ya las toma. Predicción cumplida en beneficio, fallida en reglas.
- Estado: activa (forward con libros reales, `experiments/run_h039.sh` cada 30 min desde
  2026-10-15 02:40, 7 días) | Gate: G2 parcial | Variantes: 1

### H042 [BIN] — Coherencia interna de Kalshi (cubos excluyentes y escaleras de strikes)
- Fuente: ampliación binarias; análogo de H002/H037 en Kalshi (otra base de operadores).
- Racional: en eventos de Kalshi con cubos mutuamente excluyentes (temperatura, rango de precio,
  "cuántos…") Σ asks YES < 1, o Σ asks NO < n−1, garantiza beneficio; en escaleras "above K"
  P(>K1) ≥ P(>K2) si K1 < K2. Pierde el MM lento que deja una pata desajustada. Kalshi cobra
  ceil(0.07·C·P·(1−P)) por orden, lo que penaliza cestas de muchas patas baratas.
- Protocolo G0 (fijado 2026-10-15, antes de ver datos):
  - Forward: snapshots de libros (API pública, orderbook) de todos los eventos abiertos de
    Kalshi con ≥ 2 mercados cada 60 min durante 7 días; barrido de profundidad para 10 contratos
    por pata, comisión taker ceil por pata (C=10), sin asumir fills maker.
  - Exclusividad: solo eventos con mutually_exclusive=true y cubos que cubran todo el rango
    (verificado por texto de reglas); si no se puede verificar cobertura, solo cuenta Σ NO.
  - Oportunidad: beneficio neto ≥ 0.5% del capital y anualizado ≥ 20% al cierre del evento.
  - Predicción: ≥ 150 eventos independientes con oportunidad en 7 días, beneficio medio ≥ 1 c
    por cesta-contrato. Variantes: 1.
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
- G2 (reports/h008_g2.md): copia −3.36 c (IC −4.79…−1.95); wallets a su precio +1.82 c (IC −0.23…+4.05).
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H008_copiar_wallets.md | Variantes: 1

### H004 — Deriva cerca de la resolución (decaimiento temporal)
- Fuente: dinámica temporal.
- Racional: mercados casi decididos cotizan con descuento por coste de capital y
  riesgo de resolución; ¿es el descuento mayor que el riesgo real?
- Protocolo G0 (fijado 2026-10-14, antes de ver datos de este test):
  - Universo: muestra h001 ∪ h006r, entrenamiento (closedTime < 2026-04-12), incl. anulados.
  - t = endDate − h (programado; nunca closedTime). Abierto en t. h ∈ {6h (principal), 1h}.
  - Lado favorito por prices-history en t: p ≥ 0.95 → YES; p ≤ 0.05 → NO.
  - Entrada = peor compra taker real del token favorito en (t−1h, t] (Data API); si no hay
    o si el precio real < 0.95 o ≥ 0.995 → no se opera.
  - Comisión vigente (rate del mercado o 0.07). PnL por acción = pago − precio − comisión;
    retorno anualizado por (closedTime − t).
  - Predicción falsable: PnL medio > 0 con IC95% cluster > 0, y sobrevive a quitar los
    5 mejores eventos. Se reportan las pérdidas de cola (favorito que pierde) por categoría.
  - Quién pierde: vendedores impacientes del favorito (liquidez, coste de capital).
- G2 (reports/h004_g2.md): 6h −0.43 c (IC −0.93…+0.05); 1h −1.08 c (IC −1.66…−0.53).
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H004_favoritos_cerca_cierre.md | Variantes: 2

### H011 — Mercados cripto "Up or Down" de corto plazo vs precio spot (Binance)
- Fuente: fuentes externas / dinámica temporal. Miles de mercados diarios (5 min, 15 min,
  1 h) sobre BTC/ETH. Con klines gratuitos de Binance se puede estimar la prob. justa
  (movimiento browniano con vol realizada) en cada instante y compararla con el precio
  ejecutable de PM. Quién pierde: minoristas que apuestan a dirección con precio lento.
  Riesgo: latencia (los bots ya arbitran) y comisión cripto 0.07.
- Protocolo G0 (fijado 2026-10-14, antes de descargar klines o trades):
  - Series: btc/eth × {5m, 15m, hourly}. Entrenamiento (closedTime < 2026-04-12): muestra
    aleatoria (semilla 0) de 3,000 mercados por serie (todas si hay menos).
  - Regla de resolución leída de la descripción de cada mercado: (a) TWAP Chainlink de la
    ventana ≥ precio inicial; (b) vela (cierre ≥ apertura). Proxy: klines 1m de Binance
    spot (data-api.binance.vision). G1: concordancia proxy vs resolución por serie/mes;
    si < 97% en una serie, esa serie se excluye.
  - Decisión en s = mitad de la ventana. Solo minutos de Binance cerrados antes de s.
    σ = desv. típ. de retornos log 1m de los 60 min previos.
    TWAP: E = w·A + (1−w)·S, sd = (1−w)·S·σ·sqrt(τ/3) (τ en min restantes), P = Φ((E−S0)/sd).
    Vela: P = Φ(ln(S/S0)/(σ·sqrt(τ))).
  - Ejecución: peor compra taker real del token elegido en (s+30 s, s+90 s]; comisión 0.07
    (o la del mercado). Señal: P_justa − precio − comisión ≥ 0.03 (YES o NO).
  - Predicción falsable: PnL medio > 0 con IC95% > 0, clusters = hora de inicio de ventana
    (BTC y ETH en la misma ventana correlacionan). Variantes: 1.
  - Aclaración pre-G2: s = t0 + floor(ventana/2) minutos (15m → 7 min).
- G1 (reports/h011_g1.md): en entrenamiento todas las reglas son "vela". Concordancia
  hourly 100%, 15m 98.0–98.9%, 5m 96.5–96.9% → 5m EXCLUIDAS (umbral 97%).
- G2 (reports/h011_g2.md): 3,046 apuestas, PnL −8.63 c (IC −10.04…−7.14); Brier modelo 0.169 vs PM 0.159.
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H011_cripto_updown_binance.md | Variantes: 1

### H012 — Sobre/infrarreacción tras saltos de precio
- Fuente: dinámica temporal (reacción a noticias).
- Racional: tras una noticia el precio salta; si los minoristas sobrerreaccionan, el salto
  revierte (pierden los que compran el salto); si la información se incorpora despacio,
  continúa (pierden los que venden tarde).
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Universo: muestra h001 ∪ h006r, entrenamiento. Serie horaria de prices-history en la
    ventana [end−8d, cierre].
  - Evento de salto: |p_h − p_{h−1}| ≥ 0.10 entre dos puntos horarios consecutivos, con
    0.05 < p_h < 0.95; primer salto por mercado; debe quedar ≥ 24 h hasta endDate.
  - Entrada en (t+5 min, t+65 min] al peor precio real de compra (Data API).
    Variante A (seguir): comprar el lado del salto. Variante B (revertir): el contrario.
  - Mantener hasta resolución; comisión vigente; cluster = evento.
  - Predicción falsable: una de las dos variantes con PnL > 0 e IC95% > 0. (Por simetría
    ambas pagan spread; se corrige por 2 pruebas con Holm.)
- G2 (reports/h012_g2.md): seguir −10.72 c (IC −11.70…−9.78); revertir −10.12 c (IC −11.09…−9.21).
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H012_saltos_precio.md | Variantes: 2

### H013 — Recompensas de liquidez vs selección adversa (maker pequeño)
- Fuente: microestructura (programa de recompensas, docs.polymarket.com/market-makers/liquidity-rewards).
- Racional: Polymarket paga diariamente a makers por cotizar cerca del medio
  (S = ((v−s)/v)²·tamaño; reparto proporcional; Q_min exige dos lados o divide por c=3).
  Si la recompensa por dólar inmovilizado supera la pérdida por selección adversa, hay
  borde. Quién paga: el programa de incentivos (y los takers informados contra el maker).
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Etapa 1 (rendimiento esperado, snapshots vivos): mercados con recompensas activas y
    mid en [0.10, 0.90]. Órdenes propias hipotéticas: tamaño = rewards_min_size, a
    s = v/2 del mid en ambos lados. Q_lado existente = Σ ((v−s_i)/v)²·tamaño_i de órdenes
    dentro de v. Cuota = min(q/(q+Q1), q/(q+Q2)). Recompensa/día = tasa_diaria·cuota.
    Capital = tamaño·bid + tamaño·(1−ask). Rendimiento/día = recompensa/capital.
  - Éxito etapa 1: ≥ 20 mercados con recompensa ≥ 1 USD/día y rendimiento ≥ 0.5%/día en
    la mediana de 3 snapshots (separados ≥ 4 h). Si no → rechazar.
  - Etapa 2 (solo si pasa la 1): paper trading forward con fills pesimistas (trade taker que
    cruza estrictamente nuestro nivel) para medir la selección adversa; criterio G7.
- Etapa 1 (data/h013/snap_20261014T0634.csv): 13,876 mercados evaluables; 6,203 con
  ≥1 USD/día y ≥0.5%/día; mediana 1.5%/día; top ~1000%/día con cuota 100% en libros vacíos.
  DEMASIADO BUENO → se asume error hasta demostrar lo contrario. Tasas confirmadas en Gamma
  (clobRewards), pero no hay datos públicos de pagos reales; los libros están vacíos cerca
  del medio pese a pagar 100–200 USD/día → indicio fuerte de selección adversa o de reglas
  de pago no modeladas.
- Etapa 2a (pre-registrada 2026-10-14, antes de ver datos): cota de selección adversa en
  ENTRENAMIENTO. Mercados cerrados < 2026-04-12 con clobRewards activos (raw Gamma),
  muestra aleatoria 300 (semilla 0) con mid en [0.10, 0.90] 48 h antes de endDate.
  Cotizar YES-bid y YES-ask a mid ± v/2 (mid = prices-history fidelity 1 min, solo ≤ t)
  en la ventana [end−48h, end−24h], tamaño min_size, re-cotizando cada minuto; fill solo
  si un trade taker cruza estrictamente el nivel; posiciones a resolución. Comparar pérdida
  por día con la recompensa MÁXIMA posible (tasa diaria × cuota 1). Si pérdida > recompensa
  máxima en la mediana → rechazar. Si no → etapa 2b forward (G7) con libros vivos.
- Etapa 2a (reports/h013_2a.md, 300 mercados de entrenamiento, ventana end−48h…end−24h):
  ~9 fills/día; PnL de cotización mediana 0.00 USD/día (media +0.21) vs recompensa máxima
  mediana 10 USD/día → la selección adversa NO anula la recompensa. Pasa a 2b.
- Verificación de pagos: Data API /activity?type=REWARD muestra pagos diarios reales a
  makers de mercados recompensados (p. ej. 300–2,800 USD/día a los mayores). El programa
  paga de verdad; falta saber qué cuota obtendría un maker pequeño.
- Etapa 2b (pre-registrada 2026-10-14, antes de ver datos; paper trading, sin dinero):
  - 60 mercados aleatorios (semilla 0) del conjunto recompensado actual con mid en
    [0.15, 0.85], tasa ≥ 5 USD/día, endDate en 2–10 días.
  - Cada 5 min: libros YES+NO → mid del libro combinado; órdenes propias hipotéticas a
    mid ± v/2, tamaño min_size. Cuota = min(q/(q+Q1), q/(q+Q2)) sin contarnos a nosotros
    en Q. Recompensa devengada = tasa × cuota × 5/1440 (solo si la recompensa diaria
    estimada del mercado ≥ 1 USD; si no, 0 por el mínimo de pago).
  - Fills: trades taker (Data API) del intervalo que crucen ESTRICTAMENTE nuestro nivel →
    posición de min_size al precio propio (una por lado e intervalo). Hasta resolución.
  - Duración: hasta que resuelvan los 60 o 14 días. Capital = máx. capital simultáneo.
  - Éxito: Σ(PnL + recompensas) > 0 con IC95% bootstrap por mercado > 0 y rendimiento
    mediano ≥ 0.3%/día sobre capital. Si no → rechazar.
- Estado: DESCARTADA | Gate: etapa 2b (detenida) | Motivo: el usuario la probó en real sin buenos resultados; findings/H013_recompensas_liquidez.md | Variantes: 1

### H015 — Comprar al ganador tras el final del partido (fútbol)
- Fuente: dinámica temporal (cerca de la resolución). Tras el final, el resultado es público
  pero el mercado sigue abierto hasta la resolución UMA.
- Racional: si el ganador cotiza < 1 − comisión tras el partido, comprar es casi seguro;
  pierden vendedores que necesitan liquidez antes de resolver. Riesgo: resolución errónea o
  disputa, partido aplazado/alargado.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Universo: los 10,083 mercados emparejados de H005 (fútbol), entrenamiento.
  - t = kickoff + 3 h (partido terminado con margen). Lado = el que el resultado oficial
    (football-data FTR) hace ganar.
  - Entrada = peor compra taker real del lado ganador en (t, t+2 h]; solo si precio ≤ 0.995.
  - PnL = pago − precio − comisión; rendimiento anualizado por (closedTime − t).
  - Predicción falsable: PnL > 0 con IC95% > 0 y rendimiento anualizado mediano ≥ 20%;
    se cuentan y reportan todos los casos en que el "ganador" no cobra.
- G2 (reports/h015_g2.md): 6 oportunidades en 6,821 mercados (precio ≤0.995); PnL +5.5 c pero n ínfimo.
- Estado: RECHAZADA | Gate: falla G4/G6 (frecuencia y capacidad) | Motivo: findings/H015_ganador_tras_partido.md | Variantes: 1

### H017 — Carry en NO de eventos improbables a largo plazo
- Fuente: subagente (holding rewards 4% APY en docs; "Nothing Ever Happens"). H001 solo
  probó 24h y 7d.
- Racional: compradores de lotería pagan de más por YES en eventos lejanos e improbables;
  quien vende (compra NO) cobra una prima + holding reward; coste: capital inmovilizado.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Universo: muestra h001 ∪ h006r NO sirve (solo ventana de 8 días) → nueva muestra:
    mercados de entrenamiento con duración ≥ 120 días (start ≤ end − 120d), aleatoria por
    evento (sha256 mod 1000 < 100). Precio YES en t = end − 90d por prices-history diario.
  - Señal: 0.02 ≤ p_t ≤ 0.10 → comprar NO al peor precio real de compra de NO en (t−3d, t].
  - PnL = pago − precio − comisión (+ holding reward 4%/año prorrateado SOLO si la categoría
    lo tenía documentado; si no, 0 — pesimista). Rendimiento anualizado por días hasta cierre;
    comparar con 4%/año (letra del Tesoro aprox.).
  - Clusters = evento; además informe por tema (país/persona) por correlación de colas.
  - Predicción: rendimiento anualizado medio > 4% + 2 pp con IC95% > 4%. Variantes: 1.
  - ENMIENDA (2026-10-14, antes de descargar precios): solo 6,041 mercados de entrenamiento
    cumplen duración ≥120d y abiertos en end−90d; la muestra 10% (495) es inviable → se usa
    el universo elegible completo (6,041). Sin ver precios ni resultados.
- G2 (reports/h017_g2.md): 936 ops; PnL +1.79 c (IC +0.86…+2.62); anualizado 7.87% (IC −5.81…+17.93%).
- Estado: RECHAZADA | Gate: falla G2 (criterio anualizado) | Motivo: findings/H017_carry_no_largo_plazo.md | Variantes: 1

### H016 — Mercados cripto de barrera ("reach/dip X") vs modelo de volatilidad realizada
- Fuente: subagente de investigación (fc26.ifca.ai market-efficiency paper; AAU tesis BTC).
- Racional: minoristas valoran "tocar X antes de D" como "acabar sobre X" (ignoran el
  principio de reflexión) → barreras mal valoradas, sobre todo al abrir, cerca del
  vencimiento y en fin de semana. Pierde el minorista que compra barreras lejanas.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Universo: mercados binarios "Will <BTC|ETH> reach/hit/dip to $X ..." (preguntas con
    reach/hit/dip/fall to + importe), entrenamiento. Barrera y dirección por regex; vencimiento
    = endDate. Precio de referencia: Binance spot 1m (proxy; G1 = concordancia con resolución
    ≥ 97% o se excluye la serie).
  - En t = endDate − 3d (si el mercado sigue abierto y la barrera no se ha tocado hasta t):
    P_toque = 2·Φ(−|ln(X/S_t)|/(σ·√τ)) (reflexión, sin deriva), σ = vol realizada 1m de los 7
    días previos, τ en minutos.
  - Entrada = peor compra taker real en (t−1h, t] del lado con ventaja; señal edge ≥ 0.05 neta
    de comisión. Fin de semana = estrato prefijado (se reporta, no es variante).
  - Predicción: PnL > 0 con IC95% cluster (día de vencimiento × activo) > 0. Variantes: 1.
- G2 (reports/h016_g2.md): 52 apuestas, PnL −5.56 c (IC −14.6…+4.4); Brier modelo 0.0835 vs PM 0.0770.
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H016_barreras_cripto.md | Variantes: 1

### H018 — Mercados de "mención" (¿dirá X la palabra Y?)
- Fuente: subagente (guías: el YES está sobrevalorado frente a la tasa base). 10,321
  mercados de entrenamiento (pregunta con "say"/"mention").
- Protocolo G0 (fijado 2026-10-14, antes de ver precios o resultados de esta categoría):
  - Universo: mercados de entrenamiento cuya pregunta contiene "say" o "mention".
  - t = endDate − 2h (antes del evento típico). Comprar NO al peor precio real de compra de
    NO en (t−2h, t] si el precio YES implícito (1 − precio NO) está en [0.20, 0.80].
  - PnL = pago − precio − comisión; clusters = evento (mismo discurso).
  - Predicción falsable: PnL > 0 con IC95% > 0, y se mantiene sin top-5 eventos. Variantes: 1.
  - Quién pierde: compradores de YES que sobreestiman la probabilidad de una palabra concreta.
- G2 (reports/h018_g2.md): 2,193 ops, PnL +1.04 c (IC −2.00…+3.95); sin top-5 −0.60 c.
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H018_menciones.md | Variantes: 1

### H020 — Apertura de mercados nuevos (deriva de la primera hora)
- Fuente: subagente (IMDEA: libros iniciales anchos, precio inicial puede anclar).
- Racional: al abrir, el precio se descubre con poca liquidez; si la primera hora de
  operaciones muestra una deriva clara, puede continuar (anclaje lento) o revertir.
  Pierden LPs con cotizaciones iniciales obsoletas o takers impacientes.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Universo: mercados binarios de entrenamiento (end y closedTime < 2026-04-12) con
    volumen total ≥ 5,000 USD, excluyendo series recurrentes de cripto Up/Down; muestra
    aleatoria por evento sha256(event_id) mod 1000 < 50.
  - Apertura a0 = primer trade taker del mercado. Deriva = (VWAP de trades taker en
    [a0+50min, a0+60min] del token YES) − (precio del primer trade YES). Requiere |deriva|
    ≥ 0.05 y precio YES actual en [0.10, 0.90].
  - Variante A (momentum): comprar el lado de la deriva; Variante B (reversión): el contrario.
    Entrada = peor compra taker real del token en (a0+60min, a0+120min]. Hasta resolución.
  - PnL neto de comisión; clusters = evento. Holm sobre 2 pruebas.
  - Predicción: una variante con PnL > 0 e IC95% > 0 y p corregido < 0.05.
- G2 (reports/h020_g2.md): momentum −8.6 c (IC −17.0…−0.1), reversión −18.0 c (IC −27.4…−7.9); n=90/80.
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H020_apertura_mercados.md | Variantes: 2

### H025 — Favoritos a largo plazo (YES en 0.90–0.98 a 90 días)
- Fuente: simétrico de H017 (no se miró este lado en H017).
- Racional: si a largo plazo los longshots están sobrevalorados, los favoritos pueden estar
  infravalorados (aversión a inmovilizar capital en "casi seguros").
- Protocolo G0 (fijado 2026-10-14, antes de ver datos de este lado):
  - Mismo universo, t, fuentes y ventana que H017 (entrenamiento, duración ≥120 d, t=end−90d).
  - Señal 0.90 ≤ p_t ≤ 0.98 → comprar YES al peor precio real de compra de YES en (t−3d, t].
  - Mismo criterio: anualizado medio > 6% con IC95% inferior > 4%; y PnL por acción IC > 0.
- G2 (reports/h025_g2.md): 124 ops, PnL +1.76 c (IC −1.29…+4.15); anualizado 17.5% (IC 2.0…31.3%).
- Estado: RECHAZADA | Gate: falla G2 (criterio) y G4 (n<150) | Motivo: findings/H025_favoritos_largo_plazo.md | Variantes: 1

### H024 — Carry en NO a largo plazo + holding rewards (derivada de H017)
- Fuente: H017 (borde por acción +1.8 c significativo pero anualizado insuficiente).
- AVISO de snooping: se diseña tras ver H017 en entrenamiento → el veredicto debe salir del
  HOLDOUT (G3), una sola vez, y cuenta como prueba nueva en el contador.
- Idea: limitar a mercados con holdingRewardsEnabled=true (campo de Gamma, 4% APY documentado)
  y sumar esa recompensa prorrateada; carteras diversificadas por tema.
- Protocolo (fijado 2026-10-14; G3 = HOLDOUT, UNA sola ejecución):
  - Código: experiments/h017_g2.py parametrizado; primero se reproduce H017 en entrenamiento
    (mismos números = validación del código), después UNA ejecución en holdout.
  - Universo holdout: mercados con closedTime ≥ 2026-04-12, duración ≥ 120 d, abiertos en
    end−90d, end ≤ fecha de datos. Misma señal (0.02 ≤ p ≤ 0.10 en end−90d), misma entrada
    (peor compra real de NO en (t−3d, t]), misma comisión.
  - Holding reward: +4%/año prorrateado sobre el precio solo si holdingRewardsEnabled=true en
    Gamma (valor observado tras el cierre; supuesto declarado). Se reportan ambos (con y sin).
  - Éxito: (a) PnL por acción > 0 con IC95% > 0 en holdout; y (b) anualizado medio CON holding
    reward > 6% con IC95% inferior > 4%. Si (a) sí y (b) no → sesgo confirmado pero no
    explotable frente al coste de capital.
- G3 HOLDOUT (reports/h024_g3.md, una ejecución): 471 ops / 231 eventos; PnL +1.37 c/acción
  (IC95% +0.07…+2.67); anualizado medio 13.90% (IC 6.91…21.20%); con holding reward 13.95%
  (solo 5 mercados lo tenían). Criterios (a) y (b): CUMPLE.
- En curso (2026-10-14): G4/G5 — rentabilidad de cartera (capital×tiempo), costes×2, sin
  top-5, concentración por tema, vecinos de parámetros (en ENTRENAMIENTO), corrección por
  las 24 pruebas totales; doble implementación independiente y red team (subagentes).
- Red team (reports/h024_redteam.md): anualización de cartera 6.6%; sin censura +1.18 c (IC −0.27…+2.57);
  costes×2 +0.71 c (IC incluye 0); p=0.039 vs 0.002 corregido.
- Estado: RECHAZADA | Gate: falla G4/G5 | Motivo: findings/H024_carry_no_holdout.md | Variantes: 1

### H014 — Mercados de temperatura máxima diaria vs pronóstico meteorológico
- Fuente: fuentes externas (modelos de pronóstico). Mercados "highest temperature in
  <ciudad> be <N>° on <fecha>" (eventos negRisk por tramos), muy minoristas.
- Racional: el pronóstico numérico a 1 día es muy informativo; si el precio de los tramos
  no lo refleja, hay borde. Pierden minoristas que apuestan por intuición.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Universo: mercados binarios de temperatura máxima diaria (tramos exactos, "o más",
    "o menos"), entrenamiento (closedTime < 2026-04-12).
  - Pronóstico: Open-Meteo Previous Runs API, temperature_2m_max con lead de 1 día
    (previous_day1) en las coordenadas de la ciudad → emitido ≥ 1 día antes (sin lookahead).
  - Observado = tramo que resolvió YES en el evento.
  - Modelo de error: normal por ciudad (media y sd de observado − pronóstico) estimado en la
    PRIMERA mitad temporal del entrenamiento; evaluación solo en la SEGUNDA mitad.
  - Prob. del tramo según su semántica (redondeo al entero; ≥N; ≤N).
  - t = 12:00 UTC del día anterior a la fecha objetivo. Precio = peor compra taker real en
    (t−1h, t]. Señal: prob − precio − comisión ≥ 0.05 (YES o NO).
  - Predicción falsable: PnL > 0 con IC95% cluster (ciudad-fecha) > 0. Variantes: 1.
- G2 (reports/h014_g2.md): 1,370 apuestas, PnL −1.86 c (IC −3.76…+0.02); Brier modelo 0.124 vs PM 0.105.
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H014_temperatura_pronostico.md | Variantes: 1

### H027 — Temperatura máxima del MISMO día con observaciones METAR (nowcast)
- Fuente: subagente de investigación (IEM ASOS/METAR global, con hora de observación).
- Racional: a media tarde el máximo acumulado ya descarta tramos y casi decide otros; si el
  precio tarda en reflejarlo, hay borde. Pierden minoristas que mantienen tramos muertos.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos de METAR o precios a esas horas):
  - Universo: mercados de temperatura máxima de H014 (entrenamiento, < 2026-04-12).
  - G1: máximo diario METAR de la estación de resolución vs tramo resuelto; ciudades con
    concordancia < 95% se excluyen.
  - t = 15:00 hora local de la estación en el día objetivo. Información: observaciones METAR
    con hora ≤ t − 15 min. M = máximo acumulado del día local hasta entonces.
  - Modelo: distribución empírica por ciudad de (máximo final − máximo acumulado a las 15:00),
    estimada en la PRIMERA mitad temporal del entrenamiento; prueba en la SEGUNDA mitad.
  - Precio = peor compra taker real en (t, t+10 min]. Señal: prob − precio − comisión ≥ 0.05.
  - Predicción: PnL > 0 con IC95% cluster (ciudad-fecha) > 0; Brier modelo < Brier precio.
- G2 (reports/h027_g2.md): 685 apuestas, PnL −3.25 c (IC −5.79…−0.61); Brier modelo 0.153 vs PM 0.086.
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H027_metar_mismo_dia.md | Variantes: 1

### H028 — "¿Batirá X sus beneficios trimestrales?" vs historial de batidas
- Fuente: subagente (FactSet: tasa de batida S&P 500 ~76% a 10 años; 682 mercados).
- Racional: el historial de batidas de cada empresa es público antes del informe; si el
  mercado trata el evento como ~50/50, hay borde. Pierden quienes ignoran la tasa base.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Universo: mercados binarios de entrenamiento con pregunta de "beat earnings" (o similar).
  - Prob. = (k + 0.76·4)/(n + 4), con k batidas en los últimos n ≤ 8 trimestres anteriores al
    informe (solo informes con fecha < t).
  - t = 24 h antes de la hora del informe (o de endDate si no consta). Precio = peor compra
    taker real en (t−23 h, t]. Señal: prob − precio − comisión ≥ 0.05 (YES o NO).
  - Clusters = fecha de informe. Predicción: PnL > 0 con IC95% > 0 y ≥ 150 mercados.
- G2 (reports/h028_g2.md): 250 apuestas, PnL −2.85 c (IC −7.54…+2.67); Brier modelo 0.181 vs PM 0.157.
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H028_batir_beneficios.md | Variantes: 1

### H023 — Lead-lag Kalshi → Polymarket
- Fuente: subagente. Prior bajo (PM suele liderar), exige latencia.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Universo: partidos de NFL, NBA y MLB con mercado de ganador en ambas plataformas,
    entrenamiento (closedTime PM < 2026-04-12). Emparejamiento por fecha y equipos (tabla
    versionada, 0 discrepancias de resultado exigidas como en H005).
  - Señal: movimiento del último precio de Kalshi ≥ 0.05 en una ventana de 2 min (trades
    públicos de Kalshi) sin movimiento equivalente previo en PM (|ΔPM| < 0.02 en la misma
    ventana). Solo antes del inicio del partido (pre-game), para evitar latencia en vivo.
  - Entrada en PM en la dirección del movimiento: peor compra taker real en (t+30 s, t+5 min].
    Mantener hasta resolución. Comisión vigente.
  - Predicción: PnL > 0 con IC95% cluster (partido) > 0 y ≥ 150 partidos. Variantes: 1.
- G2 (reports/h023_g2.md): 1,324 ops / 636 partidos, PnL −2.56 c (IC −4.98…−0.03); seguimiento +0.54 c.
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H023_kalshi_leadlag.md | Variantes: 1

### H032 — Número de posts semanales (Musk, Trump, Zelenskyy…) con contador XTracker
- Fuente: subagente de investigación. Eventos negRisk semanales por tramos para ~8 cuentas;
  XTracker (fuente de resolución) publica cada post con createdAt e importedAt.
- Racional: a mitad de semana el recuento acumulado + ritmo histórico de la cuenta dan una
  distribución del total; si los tramos no la reflejan, hay borde. Pierden minoristas que
  apuestan por intuición sobre el total.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Universo: eventos "<cuenta> # tweets/posts <ventana>" con historial XTracker,
    entrenamiento (closedTime < 2026-04-12). G1: recuento XTracker de la ventana vs tramo
    resuelto ≥ 97% por cuenta, si no se excluye la cuenta.
  - t = inicio de ventana + 4 días. Información: posts con importedAt ≤ t (nunca createdAt
    solo). C = recuento acumulado en la ventana hasta t.
  - Modelo: distribución empírica del número de posts en un periodo de la misma duración que
    el restante, tomada de las últimas 8 ventanas no solapadas de esa cuenta anteriores a t.
    P(tramo) = P(C + resto ∈ tramo).
  - Precio = peor compra taker real en (t, t+30 min]; señal prob − precio − comisión ≥ 0.05
    (YES o NO de cada tramo). Clusters = evento (cuenta-semana).
  - Predicción: PnL > 0 con IC95% > 0 y ≥ 150 eventos (si hay menos, se reporta inviable y
    pasa a forward). Brier modelo < Brier precio. Variantes: 1.
- G2 (reports/h032_g2.md): 188 apuestas / 49 eventos, PnL −5.37 c (IC −10.37…−0.25); Brier modelo 0.076 vs PM 0.063; solo 55 eventos usables.
- Estado: RECHAZADA | Gate: falla G2 (y G4 inviable) | Motivo: findings/H032_posts_xtracker.md | Variantes: 1

### H034 — Props de esports "Game N" que se anulan a 50-50 tras decidirse la serie
- Fuente: subagente (reglas verificadas: "If Game N is not played because the series result
  has already been determined… 50-50"). 38.5k props Game 3 (47% anulados), Game 5 (74%).
- Racional: cuando la serie ya está decidida antes del Game N, el prop vale exactamente 0.5; si
  quedan órdenes en reposo lejos de 0.5 (cotizaciones mecánicas/olvidadas), comprarlas da
  beneficio casi seguro. Pierden makers con órdenes desfasadas.
- Protocolo G0 (fijado 2026-10-14, antes de ver precios o PnL):
  - Universo: props "Game N"/"Map N" de esports con regla 50-50 en la descripción,
    entrenamiento (closedTime < 2026-04-12), con su mercado de serie (ganador de la serie) en
    el mismo evento.
  - t_d = primer trade del mercado de serie con precio ≥ 0.99 (serie decidida; dato público).
    Solo props con N = número máximo de partidas (Bo3→Game 3, Bo5→Game 5) y t_d anterior a
    cualquier trade del prop con precio ≥ 0.99 o ≤ 0.01 (indicio de que la partida N no se
    jugó). La identificación usa SOLO datos ≤ t.
  - Entrada: en (t_d + 15 min, t_d + 6 h], cada trade taker real de compra (YES o NO) a precio
    ≤ 0.5 − comisión − 0.03 se toma como ejecutable para nosotros al mismo precio (máx. 1 por
    token). Pago real según resolución (0.5 si anulado).
  - Clusters = serie. Predicción: PnL > 0 con IC95% > 0, ≥ 150 series, y tasa de anulación
    observada ≥ 90% en las operaciones (si no, la identificación falla).
- G2 (reports/h034_g2.md): 89 entradas / 65 series; anulación 0.21 (<0.90); PnL −1.9 c (IC −6.9…+3.8).
- Estado: RECHAZADA | Gate: falla G2 (identificación) y G4 (n, capacidad) | Motivo: findings/H034_esports_props_5050.md | Variantes: 1

### H035 — Ventana de disputa UMA (comprar el lado propuesto durante la disputa)
- Fuente: subagente (3,377 mercados disputados, 1,804 eventos).
- Racional: tras una disputa, el lado propuesto puede quedar infravalorado por pánico o por
  aversión a la incertidumbre de reglas. Pierde quien vende durante la disputa.
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Universo: mercados de entrenamiento con disputa (umaResolutionStatuses contiene
    "disputed"). Hora de disputa y precio propuesto desde logs on-chain del Optimistic Oracle
    (Polygon; eventos DisputePrice/ProposePrice). Sin hora de disputa fiable → inviable.
  - t = hora de la (primera) disputa + 30 min. Lado = el propuesto originalmente.
  - Entrada = peor compra taker real de ese lado en (t, t+2 h]; solo si precio ≤ 0.95.
  - Hasta resolución; comisión vigente; clusters = evento.
  - Predicción: PnL > 0 con IC95% > 0 y ≥ 150 eventos; reportar tasa de reversión
    (resolución ≠ propuesta) y rentabilidad de cartera.
- G2 (reports/h035_g2.md): 240 ops / 217 eventos; lado propuesto gana 35% a precio 0.48; PnL −13.8 c (IC −18.5…−9.1).
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H035_disputas_uma.md | Variantes: 1

### H040 [BIN] — Binarias de bróker de pago fijo vs predictibilidad del subyacente
- Fuente: ampliación. Brokers ofrecen "arriba/abajo" a 1–15 min con pago fijo 80–90% → punto
  de equilibrio de acierto = 1/(1+pago): 52.6% (90%) a 55.6% (80%).
- Protocolo G0 (fijado 2026-10-14, antes de ver datos):
  - Datos: Binance 1m BTCUSDT y ETHUSDT (data.binance.vision), 2025-01-01 → 2026-04-11
    (entrenamiento); holdout 2026-04-12 → hoy (una vez).
  - Reglas (2 variantes, Holm): momentum (signo del retorno de los 5 min previos) y reversión
    (signo contrario), horizonte 5 min, entrada en el cierre del minuto.
  - Predicción: acierto > 55.6% (pago 80%) con IC95% por día > 55.6%. Si no → rechazar y
    documentar que el valor esperado es negativo por construcción.
  - (Restricciones geográficas no se evalúan por decisión del usuario; foco en la señal.)
- G2 (reports/h040_g2.md): mejor regla (reversión ETH) 51.1% (IC 50.9–51.4%) < 55.6% (pago 80%).
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H040_binarias_broker.md | Variantes: 2

### H041 — Comprar el lado del DISPUTANTE tras una disputa UMA (derivada de H035)
- Fuente: H035 (en entrenamiento el lado propuesto ganó solo 35% tras la disputa).
- AVISO de snooping: diseñada tras ver H035 en entrenamiento → G2 en entrenamiento (cuenta como
  prueba) y veredicto final SOLO en el HOLDOUT (G3), una vez.
- Racional: un disputante arriesga su fianza; si disputa, suele tener información o razón sobre
  las reglas. El mercado puede no descontarlo del todo. Pierden quienes compran el lado propuesto
  por inercia tras la disputa.
- Protocolo (fijado 2026-10-14, antes de calcular este lado):
  - Igual que H035 (mismos mercados, mismas horas de disputa on-chain, t = disputa + 30 min),
    pero comprando el token OPUESTO al propuesto: peor compra taker real en (t, t+2 h];
    solo si precio ≤ 0.95. Hasta resolución; comisión vigente; clusters = evento.
  - Éxito G2: PnL > 0 con IC95% > 0, costes×2 > 0, sin top-5 > 0.
  - G3 (holdout, una vez): escanear logs de disputa desde 2026-04-12; mismo código. Éxito: PnL > 0
    con IC95% > 0 y ≥ 150 eventos entre G2+G3 independientes; rentabilidad de cartera reportada.
- G2 (reports/h041_g2.md): 530 ops / 426 eventos; lado disputante gana 15.3% a 0.199; PnL −5.17 c (IC −7.40…−2.94). Holdout no tocado.
- Estado: RECHAZADA | Gate: falla G2 | Motivo: findings/H041_lado_disputante.md | Variantes: 1
