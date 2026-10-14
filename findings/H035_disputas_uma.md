# H035 — Comprar el lado propuesto tras una disputa UMA — RECHAZADA en G2

**Veredicto:** el lado propuesto, comprado tras la disputa, gana solo el 35% de las veces a un
precio medio de 0.48 → PnL muy negativo. El mercado (y la disputa) aciertan contra la propuesta.

## G1 (reports/h035_g1.md)
Logs DisputePrice de los oráculos UMA V2 y Managed V2 en Polygon (hasta 2026-04-12, sin tocar
holdout). 1,647 mercados disputados de entrenamiento (1,017 eventos), 100% emparejados; mapeo
precio propuesto→token verificado contra QuestionResolved (100%). Reversión global 22.5%.

## G2 (reports/h035_g2.md)
240 operaciones en 217 eventos (de 1,619 evaluados: 992 sin compras en la ventana, 387 >0.95).
PnL −13.8 c (IC95% −18.5…−9.1); costes×2 −21.0 c; sin top-5 −15.5 c. Diagnóstico con precio
mediano: −7.1 c (IC −11.5…−2.6).

## Derivada
El lado opuesto (el del que disputa) parece infravalorado → H041, diseñada tras ver estos datos:
su veredicto debe salir del HOLDOUT (G3), una sola vez.

Implementación: subagente; 133 tests. Commit 5f1e32e. Variantes: 1.
