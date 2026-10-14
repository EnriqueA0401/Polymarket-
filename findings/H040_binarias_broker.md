# H040 [BIN] — Binarias de bróker de pago fijo a 5 min — RECHAZADA en G2

**Veredicto:** reglas simples de dirección a 5 min en BTC/ETH aciertan ~49–51%; el equilibrio con
pago 80% es 55.6% (90%: 52.6%). Valor esperado −8 a −12% por apuesta.

## Resultados (Binance 1m, 2025-01-01→2026-04-11; holdout no usado; reports/h040_g2.md)
| activo | regla | n | acierto | IC95% (por día) | VE pago 80% |
|---|---|---|---|---|---|
| BTC | momentum | 133,821 | 48.93% | 48.62–49.22 | −0.119 |
| BTC | reversión | 133,821 | 50.80% | 50.50–51.11 | −0.086 |
| ETH | momentum | 133,983 | 48.72% | 48.45–48.97 | −0.123 |
| ETH | reversión | 133,983 | 51.11% | 50.86–51.38 | −0.080 |
(Empates cuentan como fallo, pesimista.)

## Lectura
Existe una ligera reversión a 5 min (~51%, efecto rebote bid-ask), pero el pago fijo del bróker
exige ≥ 52.6–55.6%: el valor esperado es negativo por construcción. Familia "binarias de pago
fijo sobre subyacente líquido con reglas simples": descartada.

Commit 451926f. Variantes: 2 (Holm).
