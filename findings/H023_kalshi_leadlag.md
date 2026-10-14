# H023 — Lead-lag Kalshi → Polymarket (pre-partido) — RECHAZADA en G2

**Veredicto:** PM sigue a Kalshi pero solo ≈ +0.5 c en 5 min, muy por debajo de los costes;
copiar los movimientos de Kalshi pierde.

## G1 (reports/h023_g1.md)
3,974 partidos de entrenamiento emparejados (MLB 2,361 / NBA 1,333 / NFL 280); resoluciones
coinciden en 3,970 (3 discrepancias excluidas). 1,519 con movimiento Kalshi ≥ 0.05.

## G2 (reports/h023_g2.md; holdout NO tocado)
1,324 operaciones (de 5,090 señales) en 636 partidos: PnL −2.56 c (IC95% −4.98…−0.03);
costes×2 −5.31 c; sin top-5 −3.50 c. Placebo (−10 min): +1.62 c (IC −0.87…+4.24).
Seguimiento medio de PM en 5 min: +0.54 c (placebo +0.03).

Decisiones de implementación fijadas antes del PnL (ver informe): un mercado Kalshi por partido,
ventana de entrada antes del inicio, precio PM previo conocido, bloqueo de 5 min tras señal,
dobles jornadas excluidas, comisión del mercado o 0.07. Implementación: subagente; 108 tests.
Commit 1ffc6e2. Variantes: 1.
