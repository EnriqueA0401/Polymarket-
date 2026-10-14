# H016 — Barreras cripto ("reach/dip") vs modelo de volatilidad — RECHAZADA en G2

**Veredicto:** el modelo de reflexión con volatilidad realizada es PEOR que el precio
ejecutable de Polymarket; las apuestas pierden y la muestra es pequeña (37 clusters).

## G1 (reports/h016_g1.md)
- 2,805 mercados de entrenamiento (292 eventos). Resolución casi siempre Binance 1m High/Low;
  13 "reach" resuelven por Low ≤ X (se usa la regla de la descripción). Concordancia del proxy
  99–100% por grupo; se excluye solo un grupo "hashprice" (4 mercados).

## G2 (reports/h016_g2.md; holdout NO tocado)
- 1,284 elegibles; 52 apuestas (38 eventos, 37 clusters): PnL −5.56 c/acción
  (IC95% −14.6…+4.4); costes×2 −8.2 c; sin top-5 clusters −15.1 c (IC −22.2…−7.9).
- Barreras "up" (comprar el toque): −15 c, significativo.
- Brier modelo 0.0835 vs precio ejecutable 0.0770 (dif. +0.0066, IC +0.0013…+0.0122).
- Muy por debajo de 150 clusters independientes.

## Sustituciones de protocolo (fijadas antes de G2, ver informe)
Train exige end y closedTime < holdout; toque comprobado desde startDate; exponente de la
comisión ignorado (pesimista); costes×2 = comisión×2 + deslizamiento extra; τ hasta endDate;
cluster = día UTC × activo. Implementación: subagente; revisada y tests (63) en verde.

Commit 9048623. Variantes: 1.
