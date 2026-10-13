# H003 — Sobreprecio de "Yes" — RECHAZADA (artefacto de precios no ejecutables)

**Veredicto:** el aparente borde (+8.7% neto a 7d) existe solo en precios de prices-history
que no eran ejecutables. Con precios reales de compra de NO el retorno es negativo.

## Evidencia (entrenamiento, closedTime < 2026-04-12; holdout NO tocado)
| horizonte | señales | con compras reales de NO en (t−24h,t] | ret. precio hist.+0.02 (esas ops) | ret. peor precio real | IC95% cluster |
|---|---|---|---|---|---|
| 24h | 8,287 | 4,046 (48.8%) | −1.41% | −11.04% | −13.3%…−8.6% |
| 7d  | 5,159 | 968 (18.8%)   | +2.34% | −5.90%  | −12.5%…+0.6% |

- Precio real de NO − (1−p histórico): +0.09 de media → p histórico no refleja el ask.
- En la muestra completa (sin exigir trades) 7d daba +8.7%: el "borde" se concentraba en
  mercados sin compradores reales de NO (no ejecutable).
- Libros vivos en zona 0.2–0.8 de mercados Yes/No: spread mediano 0.77
  (reports/h003_live_costs.md).
- Contaminación declarada en G0 (vi la calibración agregada antes); no afecta al rechazo.

## Lección metodológica (aplica a todas las hipótesis)
prices-history NO es un precio ejecutable fuera de mercados líquidos. Toda hipótesis que
opere en la zona media o en mercados poco negociados debe usar precios de trades reales
(Data API, takerOnly, ventana ≤ t) o libros vivos (forward).

## Reproducir
python experiments/h003_g2.py; python experiments/h001_live_costs.py h003;
python experiments/h003_exec.py (caché data/trades_h003). Commit 621ca16. Variantes: 3.
