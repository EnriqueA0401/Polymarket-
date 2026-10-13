# H001 — Sesgo favorito-longshot — RECHAZADA en G2

**Veredicto:** el sesgo existe (los longshots están sobrevalorados) pero es menor que el coste
real de ejecución como taker. No explotable.

## Datos
- Universo: 4,098,432 mercados binarios cerrados (Gamma, completo, incl. anulados). Hash
  universo 72ec51eb880d9d2d…; ver data_manifest.json. Commit de análisis 9a4507d.
- Muestra aleatoria por evento (sha256(event_id), fijada antes de ver precios): 107,174
  mercados; entrenamiento (closedTime < 2026-04-12): 63,152 mercados / 26,744 eventos.
- Holdout NO tocado.

## Resultados (entrenamiento)
| horizonte | operaciones | eventos | borde bruto (c/acción) | neto costes×1 | IC95% neto | neto costes×2 |
|---|---|---|---|---|---|---|
| 24h | 10,937 | 2,870 | +0.95 (0.70…1.19) | −0.30% | −0.56%…−0.06% | −1.00% |
| 7d  | 3,448  | 1,125 | +1.24 (0.84…1.64) | −0.12% | −0.54%…+0.29% | −0.86% |

Calibración (24h): bin [0.05,0.10) precio medio 0.071 vs frecuencia 0.046; bin ≥0.95
precio 0.984 vs 0.990. Dirección favorito-longshot confirmada.

## Coste real (reports/h001_live_costs.md)
600 libros CLOB vivos en zona de señal: coste de compra vs mid mediana 1.4 c, media 1.7 c
(10 USD a 200 USD casi igual), + comisión taker ≈ 0.2–0.5 c. 14% sin profundidad para 200 USD.
Coste total ≈ 2 c > borde bruto ≈ 1 c.

## Quién pierde / por qué no basta
Pierden los compradores de longshots, pero el market maker captura el sesgo vía spread:
el borde queda dentro del spread.

## Limitaciones
- prices-history no es bid/ask; no hay historial de libro → no se puede filtrar por spread
  bajo en el pasado sin lookahead (25% de libros vivos cuestan ≤0.8 c: solo comprobable en
  paper trading).
- Riesgo de endDate editado ex post (no verificado; no cambia el veredicto).
- Variantes usadas: 3 (24h, 7d, diagnóstico bruto). Reproducir: python experiments/h001_g2.py;
  python experiments/h001_gross.py; python experiments/h001_live_costs.py.

## Derivadas
- H006 (maker en extremos) y H007 (filtro de spread, solo forward) añadidas a la cola.
- Anomalía en bins 0.4–0.6 (precio > frecuencia) probablemente por puntos iniciales 0.5 sin
  negociar; tratar con cuidado en H003.
