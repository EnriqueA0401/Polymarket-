# H027 — Temperatura del mismo día con observaciones METAR — RECHAZADA en G2

**Veredicto:** a las 15:00 locales el precio de PM ya incorpora el máximo observado mucho mejor
que un nowcast con METAR; las apuestas pierden. La parte "obvia" (tramos muertos) se cierra
antes de poder operarla (37% de mercados ya cerrados en t).

## G1 (reports/h027_g1.md)
Concordancia METAR vs tramo resuelto 98.5% global; 45/49 ciudades pasan (excluidas Seúl 88%,
Shenzhen 23%, Hong Kong 0%, Taipéi 68%; HKO/CWA sin METAR).

## G2 (reports/h027_g2.md; corte 2026-02-18; holdout NO tocado)
685 apuestas en 380 eventos: PnL −3.25 c (IC95% −5.79…−0.61); costes×2 −7.18 c; sin top-5
−4.35 c. Brier modelo 0.153 vs precio 0.086 (dif. +0.067, IC +0.056…+0.079).

Implementación: subagente; 97 tests en verde. Commit dd178d5. Variantes: 1.
