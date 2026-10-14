# H004 — Favoritos casi decididos cerca del cierre — RECHAZADA en G2

**Veredicto:** comprar el favorito (precio real 0.95–0.995) 6 h o 1 h antes de endDate
pierde dinero: la frecuencia de acierto es menor que el precio pagado.

## Resultados (entrenamiento, muestra h001 ∪ h006r; holdout NO tocado; reports/h004_g2.md)
| h | operaciones | eventos | precio medio | acierto | PnL c/acción | IC95% cluster |
|---|---|---|---|---|---|---|
| 6h | 3,535 | 2,493 | 0.9830 | 0.9799 | −0.43 | −0.93…+0.05 |
| 1h | 3,592 | 2,718 | 0.9829 | 0.9733 | −1.08 | −1.66…−0.53 |

- Sin los 5 mejores eventos: −0.45 c / −1.12 c. 71 y 96 pérdidas de cola.
- Lectura: el "descuento" del favorito no paga el riesgo real; los compradores taker de
  favoritos pagan de más (coherente con H001: el borde queda del lado del market maker).

## Reproducir
python experiments/h004_g2.py (caché data/trades_h004). Commit d940ce8. Variantes: 2.
