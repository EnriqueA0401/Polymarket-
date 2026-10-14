# H011 — Cripto Up/Down vs Binance — RECHAZADA en G2

**Veredicto:** cuando un modelo browniano con datos de Binance discrepa ≥ 3 c del precio
ejecutable de Polymarket, Polymarket tiene razón. PnL −8.6 c/acción.

## Datos y G1
- 18,000 mercados de entrenamiento (BTC/ETH × 5m/15m/hourly, 3,000 por serie). Regla en
  entrenamiento: vela (cierre ≥ apertura). Concordancia proxy Binance: hourly 100%,
  15m 98–99%, 5m 96.5–96.9% → 5m excluidas (umbral pre-registrado 97%).

## G2 (reports/h011_g2.md; holdout NO tocado)
- Decisión a mitad de ventana con minutos de Binance cerrados; entrada al peor precio
  taker real en (s+30 s, s+90 s]; comisión 0.07·p(1−p).
- 3,046 apuestas: PnL −8.63 c (IC95% −10.04…−7.14). Todas las series negativas
  (−6.9 a −11.3 c). Edge esperado por el modelo +7.9 c → el modelo estaba equivocado.
- Brier: modelo 0.1688 vs PM 0.1592 (n=10,763).

## Lectura
Estos mercados los arbitran bots de baja latencia: con 30–90 s de retraso la información
de spot ya está en el precio. Un enfoque de latencia (segundos) queda fuera del alcance
(capital < 1,000 USD, sin infraestructura co-localizada) y su backtest con trades
históricos sería optimista sobre los fills.

## Reproducir
python experiments/h011_g1.py; python experiments/h011_g2.py. Commit fe1dff1. Variantes: 1.
