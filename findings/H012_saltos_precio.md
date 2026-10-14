# H012 — Sobre/infrarreacción tras saltos — RECHAZADA en G2

**Veredicto:** ni seguir ni revertir saltos horarios ≥ 10 c es rentable a precios reales;
ambas direcciones pierden ≈10 c, señal de spreads de ≈20 c donde ocurren los saltos.

## Resultados (entrenamiento h001 ∪ h006r; holdout NO tocado; reports/h012_g2.md)
- 68,495 saltos (22,904 eventos). Entrada en (t+5 min, t+65 min] al peor precio real.
- A seguir: 7,242 ops, PnL −10.72 c (IC −11.70…−9.78).
- B revertir: 7,893 ops, PnL −10.12 c (IC −11.09…−9.21).
- Holm (2 pruebas): ninguna significativa a favor.

## Lectura
Los saltos se concentran en mercados poco líquidos (prices-history ruidoso); comprar
cualquiera de los dos lados cuesta el spread completo. Coherente con H003.

## Reproducir
python experiments/h012_g2.py (caché data/trades_h012). Commit bb6fd46. Variantes: 2.
