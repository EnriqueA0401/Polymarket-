# H024 — Revisión por checklist + red team (pasos 5 y 6 del protocolo)

- Revisor: subagente independiente, objetivo REFUTAR. Commit revisado 8a99b41 (código de
  experiments/h017_g2.py idéntico a cbfa6c3). Fecha 2026-10-14.
- Datos: data/h024_trades.parquet (holdout, sha256 15e92527891eca76…, extraído con `holdout extract`,
  coincide con reports/h024_g3.md) y una reconstrucción del entrenamiento con la misma lógica
  (936 ops, +1.785 c, 7.87%: idéntico a reports/h017_g2.md; sha256 563d960afb2e6e96…).
  NO se ha hecho ninguna evaluación nueva sobre el holdout: solo análisis del fichero por
  operación ya existente y de la caché de trades de esas mismas entradas.
- Reproducir: `python experiments/h024_redteam.py` (usa data/h017_trades.parquet y
  data/h024_trades.parquet). Cifras de abajo = salida de ese script.

## Veredicto

**El candidato NO sobrevive como estrategia explotable.** El sesgo por acción (NO a 90 días en
YES 2–10% paga ~+1.4/+1.8 c) es real en entrenamiento y del mismo signo en holdout, pero:
1. El criterio (b) "CUMPLE" se apoya en una métrica sesgada (media de rendimientos anualizados
   por operación). Con la rentabilidad correcta sobre capital×tiempo el holdout da **6.64%
   (IC95% 0.1…12.8%)** → IC inferior < 4%: **(b) NO se cumple**.
2. El criterio (a) depende de un sesgo de censura a favor: quitando las 31 operaciones con
   endDate posterior a la fecha de datos (todas NO ganadas por eliminación temprana mientras
   sus hermanos —incluido el futuro ganador— siguen abiertos y fuera del universo), el PnL es
   **+1.18 c (IC −0.24…+2.48)**: el IC incluye 0.
3. Falla G4 (costes ×2: +0.71 c, IC −0.62…+1.98; cartera 3.4%/año) y G5 (p≈0.04 bilateral frente
   a umbral Holm/Bonferroni ≈0.002 con 25 pruebas).
4. Con < 1,000 USD la rentabilidad realista sobre capital (cartera igual-ponderada, capital
   ocioso incluido) es **~2.9%/año en holdout y ~2.3%/año en entrenamiento**, por debajo de la
   letra del Tesoro (4%).

Recomendación: cerrar H024 como "sesgo confirmado, no explotable" (rama del protocolo "(a) sí y
(b) no", leída de forma pesimista). Sub-grupos que parecen buenos (no-negRisk, entradas tras
2026-04-12) son post-hoc: solo valen como hipótesis nuevas a validar en forward/paper (G7).

## 1. Checklist de código

| Punto | Resultado |
|---|---|
| Precio en t (prices-history diario) | OK. Verificado contra serie horaria en 4 mercados: el punto diario con ts T es el precio EN T (no el cierre de T+24h). `price_at` usa solo ts ≤ t, staleness 3 d. Sin lookahead. |
| Filtro `closed_time > end − 90d` | OK en sí (estar abierto en t es observable en t). Pero ver censura abajo. |
| endDate editado ex post | NO VERIFICABLE. `end` es el valor final de Gamma; si se amplió/acortó tras t, t=end−90d no es el t que un operador habría calculado. 56/936 mercados de entrenamiento tienen end de mercado ≠ end del evento (>1 d). No hay historial de endDate → limitación; solo G7 lo resuelve. Riesgo moderado, dirección desconocida. |
| División train/holdout por `closed_time` del MERCADO | PROBLEMA. 319/471 entradas del holdout tienen t < 2026-04-12 (solapan el periodo de entradas de entrenamiento); eventos multi-mercado quedan partidos (40 ops de entrenamiento y 121 de holdout pertenecen a eventos con hermanos al otro lado). Lo correcto: dividir por evento completo y por fecha de entrada. |
| Censura al final de los datos (supervivencia) | PROBLEMA SERIO. Universo = solo mercados `closed=true` ingeridos ~2026-10-12. 31 operaciones del holdout tienen end > fecha de datos (World Series, WNBA, MVP…): entran porque cerraron NO por eliminación; sus hermanos aún abiertos (incluido el que resolverá YES) no están. Además 44 mercados largos con end pasado siguen sin cerrar (p. ej. elecciones Brasil, LA, Líbano) y quedan fuera. Ver tabla §2. |
| YES/NO invertidos | OK. token_yes=outcome0, y=1 si outcome0 gana; se compra outcomeIndex 1 y paga 1−y. Coherente aunque las etiquetas no sean Yes/No. p medio YES ≈ 1 − px medio. |
| Anulados | OK (0 anulados; y=0.5 si precios finales ≠ [1,0]/[0,1]). 11/936 mercados de entrenamiento tuvieron disputa UMA: todos resolvieron NO. |
| Fills | Discutible. "Peor compra taker de NO en (t−3d, t]" es ≈0.5 c peor que la mediana de esas compras (pesimista frente al precio típico), pero es un precio PASADO, no un ask en t, y no dice nada de tamaño: mediana de compras taker de NO en la ventana = **97 USD** (holdout), 26% de ventanas con una sola compra, solo 21% con ≥1,000 USD. Exige actividad previa (471/981 señales con compra → 52% de las señales no se pueden valorar). La API respeta start/end (0 trades fuera de ventana en 126k) → sin sesgo por truncado. |
| Comisiones | OK. feeSchedule por mercado (exponent 1, takerOnly, rate 0.03–0.07; 0.07 si falta). Impacto ≤0.3 c a px≈0.96. Holding rewards: 5/471 mercados, irrelevante (y el flag se observó tras el cierre). |
| Slippage | No modelado más allá del peor trade observado; ver costes ×2. |
| Tamaño de posición | No modelado: PnL por acción equiponderado. Ver §2 (capital). |
| Anualización | **ERROR METODOLÓGICO.** `ann = pnl/px·365/días` promediado por operación: sobrepondera operaciones cortas y ganadoras (las 11 pérdidas del holdout son todas de ~90 días). Rentabilidad económica correcta = Σpnl / Σ(px·días)·365: **6.64%** (holdout) vs 13.90% reportado; entrenamiento 8.42% vs 7.87%. En entrenamiento, 8 operaciones de <7 días aportan 3.7 pp del 7.87% medio (sin ellas 4.1%). |
| Clustering | Insuficiente. Cluster = event_id; temas correlacionados entre eventos (mismo jugador en varios Grand Slams, "Republican/Democrat win" en muchos estados, "Fed cuts" por reunión). Cluster por tema (heurística de pregunta): IC del PnL holdout **−0.29…+2.72**. |
| NaN / semillas | OK. Bootstrap con semilla 0; mercados sin precio diario se descartan (holdout 11% vs entrenamiento 4% sin precio — probablemente fallos de red sin caché de historiales; no hay razón para que dependa del resultado, pero no está comprobado ni es reproducible: los historiales no se guardan). |
| Reproducibilidad | Parcial: prices-history no se cachea → cada ejecución re-descarga; el resultado puede cambiar si la API cambia. Guardar los historiales y su hash. |

## 2. Red team: objeciones ordenadas por gravedad (con pruebas)

Cifras: PnL c/acción (IC95% bootstrap por evento); "cartera" = Σpnl/Σ(px·días)·365 (IC por evento).

| # | Objeción | Prueba | Entrenamiento | Holdout |
|---|---|---|---|---|
| 1 | Métrica anualizada sesgada; con capital×tiempo no supera 4% con confianza | cartera | 8.42% (3.5…12.5) | **6.64% (0.1…12.8)** |
| 2 | Censura de fin de datos a favor (eventos incompletos) | quitar end > 2026-10-12 | — | **+1.18 c (−0.24…+2.48)**, cartera 5.5% (−0.9…12.0) |
| 2b | + quitar eventos partidos por la frontera train/holdout | | 1.70 c (0.66…2.62) | +0.76 c (−0.99…+2.44) |
| 3 | Costes ×2 (G4) | +0.5 c slippage y comisión ×2 | 1.02 c (0.04…1.82), cartera 4.8% | **0.71 c (−0.62…+1.98), cartera 3.4%** |
| 3b | | +1 c y comisión ×2 | 0.52 c (−0.50…+1.39) | 0.21 c (−1.04…+1.54) |
| 4 | Capital real < 1,000 USD: oportunidades agrupadas (p. ej. 399/936 entradas de entrenamiento en 2025T4 por mercados "before 2026") → capital ocioso | cartera igual-ponderada, capital = pico de posiciones simultáneas | máx. 370 simultáneas, uso 26%, **2.3%/año** | máx. 319, uso 42%, **2.9%/año**; 1,000 USD → ~3 USD/posición (< mínimo de 5 acciones en muchos casos) |
| 5 | Comparaciones múltiples (G5) | z del PnL holdout | t≈4.0 (p≈7e-5: el sesgo por acción sobrevive) | z=2.06, p=0.039 bilateral ≫ 0.05/25=0.002 → **no sobrevive Holm/Bonferroni** |
| 6 | Correlación entre eventos (temas) | cluster por tema / 1 mercado por evento | tema 0.74…2.67; 1/evento 2.04 c (0.87…3.12) | **tema −0.29…+2.72; 1/evento 1.67 c (−0.31…+3.41)** |
| 7 | Fragilidad de cola: pocas pérdidas lo deciden | nº de YES adicionales que anulan el PnL | 16.7 (obs. 19, implícitos 38) | **6.4** (obs. 11, implícitos 18) ≈ 2 σ de Poisson |
| 8 | Heterogeneidad / cambio de régimen | por subgrupo | negRisk 1.24 c (−0.16…2.46) vs no-negRisk 2.38 c | negRisk **0.33 c (−1.54…+1.98)** (69% de las ops) vs no-negRisk 3.6 c; entradas t<2026-04-12 ≈ +0.5 c vs t≥ +3.1 c |
| 9 | Liquidez de entrada / el borde vive donde no se puede ejecutar | PnL por tercil de volumen; ventanas con ≥500 USD de compras NO | terciles 1.2/2.0/2.2 c; líquidos 3.1 c (2.0…4.0) | terciles **2.8/2.0/−0.7 c**; líquidos 1.6 c (−0.8…+3.8), n=134/71 ev |
| 10 | Dependencia de pocos eventos | quitar 5 mejores mercados / eventos | 1.71 / 1.61 c | 1.19 / 0.99 c (no destruye, pero el problema es la cola, #7) |
| 11 | Riesgo de resolución UMA | historial umaResolutionStatuses | 11 disputas, todas NO (a favor) | sin disputas en las 471; 44 mercados largos aún sin resolver excluidos (incl. elecciones aplazadas: reglas de aplazamiento no analizadas) |
| 12 | endDate ex post, salida antes de resolución, cambios de comisión | no comprobable con datos actuales | — | Comisión: impacto ≤0.3 c, menor. Salida anticipada: no estudiada (libro fino → vender NO a 0.96 cuesta ≥1 c). |

Lectura: el único subgrupo robusto en ambos periodos es "no negRisk" (2.4 c y 3.6 c), y las
entradas posteriores a 2026-04-12 (+3.1 c, 152 ops/84 eventos; 2.9 c sin censura, 121/68). Son
cortes elegidos tras ver el holdout → prohibido usarlos para aprobar H024. Si se quiere seguir:
nueva hipótesis pre-registrada (p. ej. "carry NO 90 d, solo mercados binarios no negRisk, cartera
1 mercado/evento, métrica capital×tiempo") validada SOLO en forward/paper trading con libro real.

## 3. Respuestas que el investigador principal debe dar por escrito
1. Recalcular el criterio (b) con capital×tiempo (o justificar por qué la media por operación es
   la métrica económica correcta). Con la métrica correcta (b) falla.
2. Tratar la censura: evaluar solo eventos completamente resueltos a la fecha de datos y
   dividir por evento/fecha de entrada. Con la censura eliminada, (a) falla.
3. Contar H024 en el contador global (25 pruebas) y aplicar Holm: falla.
4. Documentar la capacidad real (mediana ~100 USD de compras de NO en 3 días) y la rentabilidad
   de una cartera de <1,000 USD con capital ocioso (~2–3%/año).
