# H014 — Temperatura máxima diaria vs pronóstico (Open-Meteo) — RECHAZADA en G2

**Veredicto:** el precio ejecutable de Polymarket predice mejor que un modelo con pronóstico
numérico disponible en t; las apuestas pierden.

## G1 (reports/h014_g1.md)
23,574 mercados de entrenamiento (2,716 eventos, 49 ciudades) parseados al 100%; estación de
resolución identificada en todos; cobertura de pronóstico 100%; 2,689 eventos con exactamente
un tramo YES. Error observado−pronóstico: media +0.48 °C, sd 1.66.

## G2 (reports/h014_g2.md; modelo de error en eventos < 2026-02-18, prueba desde esa fecha)
- 1,370 apuestas en 499 eventos: PnL −1.86 c/acción (IC95% −3.76…+0.02); costes×2 −4.49 c
  (IC −6.42…−2.62); sin top-5 −2.50 c (IC −4.43…−0.69). Edge esperado +14.2 c → modelo erróneo.
- Brier modelo 0.1239 vs precio 0.1054 (dif. +0.0185, IC +0.015…+0.023); log loss también peor.

## Sustituciones (necesarias para evitar lookahead; ver informe)
previous_day1 de Open-Meteo usaba runs posteriores a t → se usó el lead más corto publicado
(+6 h de retraso) antes de t; máximo diario de horas locales de la estación; °F a °C; HK/Taipéi
redondeo entero; ajuste de error por máxima verosimilitud por intervalo; ciudades con <10
eventos excluidas; comisión 0.07 por defecto (diagnóstico con comisión 0: −1.10 c).
Implementación: subagente; 72 tests en verde. Commit 63189f2. Variantes: 1.
