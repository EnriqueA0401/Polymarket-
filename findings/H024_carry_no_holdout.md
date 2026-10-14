# H024 — Carry en NO a 90 días (+ holding rewards) — RECHAZADA en G4/G5 tras red team

**Veredicto:** pasó G3 con la métrica pre-registrada, pero esa métrica estaba mal definida
(media de anualizados por operación) y el holdout tenía censura favorable. Corregido, ningún
criterio se cumple. El sesgo por acción es real (entrenamiento t≈4; holdout mismo signo) pero
NO explotable para < 1,000 USD.

## Evidencia
- G2 entrenamiento (H017): +1.79 c (IC +0.86…+2.62). Doble implementación independiente
  idéntica (reports/h017_indep.md).
- G3 holdout (reports/h024_g3.md, una ejecución): +1.37 c (IC +0.07…+2.67), "anualizado medio"
  13.9% → criterios cumplidos en apariencia.
- Red team (reports/h024_redteam.md) y verificación propia (data/h024_trades.parquet).

## Respuesta escrita a cada objeción del red team
1. Anualización: ACEPTADA. La media de anualizados por operación sobrepondera ganadoras cortas.
   Rentabilidad de cartera Σpnl/Σ(precio·días)·365 = 6.64% (verificado) → criterio (b) falla.
   Error de diseño del protocolo, documentado; no se re-prueba en holdout.
2. Censura al final de los datos: ACEPTADA. 31 operaciones con endDate posterior al corte
   (todas NO por eliminación temprana; sus hermanos abiertos quedan fuera). Sin ellas:
   +1.18 c, IC −0.27…+2.57 (verificado) → criterio (a) falla.
3. Costes×2: ACEPTADA. +0.71 c (IC −0.62…+1.98) → falla G4.
4. Capital < 1,000 USD con capital ocioso: ACEPTADA. ~2.9%/año (< 4% sin riesgo); mediana de
   liquidez de NO en la ventana ≈ 97 USD.
5. Pruebas múltiples: ACEPTADA. p=0.039 frente a ≈0.002 (Holm/Bonferroni con 25 pruebas).
6. Correlación por tema: ACEPTADA. IC por tema −0.29…+2.72; 6.4 YES adicionales anulan el PnL.
7. Heterogeneidad negRisk: ANOTADA. negRisk (69%) +0.33 c (IC incluye 0). Subgrupos favorables
   (no-negRisk +3.6 c) son post hoc → solo como hipótesis nueva forward (H026).
Comprobaciones superadas: sin lookahead en precio diario, YES/NO correctos, comisiones,
start/end de Data API respetados, 11 disputas UMA resolvieron NO.

## Lecciones metodológicas (incorporadas a reports/costs.md)
- Rentabilidad siempre a nivel de cartera (capital × tiempo), nunca media de anualizados.
- Censura: en holdout usar solo eventos cuyo endDate y todos sus mercados hermanos estén
  resueltos antes del corte.

Commit 8a99b41. Variantes: 1 (holdout consumido para esta familia).
