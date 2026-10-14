# H008 — Copiar wallets rentables — RECHAZADA en G2

**Veredicto:** copiar con 60 s de retraso a las 50 wallets más rentables del semestre
anterior pierde −3.4 c/acción (IC95% −4.8…−1.9). La habilidad apenas persiste y el precio
se mueve en contra del copiador.

## Diseño (pre-registrado)
- Formación F (2025-07→2025-12): 26,689 mercados (muestra, vol ≥ 10k), 23.2M trades
  taker; 55,968 wallets con ≥20 trades en ≥10 eventos; ranking PnL/sqrt(n); top 50.
- Test T (2026-01-01→2026-04-11, antes del holdout): cada primera compra de una top wallet
  por token; entrada al peor precio real de compra en (ts+60 s, ts+660 s]; comisión vigente.

## Resultados (reports/h008_g2.md)
- 4,409 copias ejecutables (1,691 eventos, 33 wallets): PnL −3.36 c (IC −4.79…−1.95),
  retorno −7.2%, acierto 52.4% a precio medio 0.545.
- Diagnóstico: las mismas wallets a SU precio en T: +1.82 c (IC −0.23…+4.05), 50% de
  ellas con PnL>0 → persistencia débil; el copiador paga ≈5 c de deslizamiento.

## Quién gana / pierde
El operador original (o quien reacciona antes) captura el movimiento; el copiador
retrasado compra después del impacto y paga el spread.

## Limitaciones
- Formación con ≤10,000 trades más recientes por mercado (truncamiento en mercados enormes).
- Solo compras; no se modela salida anticipada.
- Variantes: 1 (+ diagnóstico no operable). Commit 87dcff8. Reproducir: python experiments/h008.py;
  python experiments/h008_diag.py.
