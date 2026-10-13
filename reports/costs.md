# Modelo de costes (verificado 2026-10-12, docs.polymarket.com/trading/fees)

- Comisión taker por operación: fee = C × feeRate × p × (1 − p)  (C = acciones, p = precio).
- Makers: 0 comisión (reciben rebate). Rebates NO se cuentan a favor (pesimista).
- feeRate por categoría: Crypto 0.07; Sports 0.05; Finance/Politics/Mentions/Tech 0.04;
  Economics/Culture/Weather/Other 0.05; Geopolitics 0.
- Gamma expone feeSchedule por mercado ({rate, exponent, takerOnly}). Regla de backtest:
  usar el rate del mercado si existe; si no, 0.07 (máximo, pesimista), aunque el mercado
  histórico no cobrara comisión — la estrategia se operaría con las comisiones de hoy.
- Spread/slippage: no existe historial de libro. prices-history da un precio por punto
  (no bid/ask). Supuesto pesimista: pagar medio spread de max(0.01, tick) + 0.01 de
  slippage por encima del precio observado (total 0.02 por acción al entrar) y G4 ×2.
- Gas/deposito: Polygon, < 0.01 USD por operación; se ignora frente a lo anterior salvo
  en tamaños < 5 USD.
- Limitación: los precios históricos pueden no ser ejecutables; se validará en G7 con libro real.

- LECCIÓN H003 (2026-10-14): prices-history no es ejecutable en mercados poco líquidos
  (zona media: precio real de NO ≈ 0.09 peor que 1−p). Usar trades reales o libros vivos.
