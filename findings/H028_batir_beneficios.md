# H028 — "¿Batirá X sus beneficios?" vs historial de batidas — RECHAZADA en G2

**Veredicto:** el precio de PM ya incorpora la tasa base de batidas (y más); el modelo de tasa
base pierde y está peor calibrado.

## G1 (reports/h028_g1.md)
683 mercados de entrenamiento (417 empresas, 101 fechas de informe), 72.8% YES. Regla: YES solo
si el EPS ajustado supera estrictamente el consenso fijado al crear el mercado. Historial de
sorpresas (Yahoo/yfinance) en 406/417 tickers; concordancia fuente vs resolución 93.1%.

## G2 (reports/h028_g2.md; holdout NO tocado)
250 apuestas en 77 fechas: PnL −2.85 c (IC95% −7.54…+2.67); costes×2 −7.03 c (IC −11.9…−1.4);
sin top-5 −5.59 c. Brier modelo 0.1806 vs precio 0.1574 (dif. +0.023, IC +0.013…+0.033).

Sustituciones: historial vía yfinance (Nasdaq solo 4 trimestres); hora del informe de Yahoo
(coincide con el cierre); comisión 0.07 por defecto. Implementación: subagente; 98 tests.
Commit f6b4dca. Variantes: 1.
