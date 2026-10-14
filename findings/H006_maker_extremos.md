# H006 — Market making en extremos — RECHAZADA (G2 + réplica pre-registrada)

**Veredicto:** el maker obtiene fills (~43%) pero la selección adversa se come casi todo
el sesgo favorito-longshot. PnL no distinguible de 0 en dos muestras disjuntas.

## Regla (pre-registrada)
Señal en t = end − h con p_t: 0.02<p≤0.10 → ofrecer YES a p+0.01; 0.90≤p<0.98 → pujar YES
a p−0.01. Fill solo si un trade taker real en (t, t+24h] cruza ESTRICTAMENTE el nivel; fill
al precio propio, una vez. Sin comisión (maker), sin rebates.

## Resultados (entrenamiento; holdout NO tocado)
| muestra | h | señales | fill | PnL c/acción | IC95% cluster | PnL sin selección |
|---|---|---|---|---|---|---|
| G2 (hash<150) | 24h | 4,698 | 43.0% | +0.63 | −0.43…+1.63 | +2.88 |
| G2 (hash<150) | 7d | 1,621 | 28.8% | +0.14 | −2.04…+2.22 | +3.25 |
| Réplica (hash 150–449) | 24h | 9,059 | 43.6% | +0.27 | −0.54…+1.03 | +2.25 |

## Lectura
- El sesgo existe (+2–3 c si todo se llenara) pero los fills llegan cuando hay información:
  los takers que cruzan saben algo. Quién gana: takers informados; quién pierde: el maker.
- Coherente con H001: el borde favorito-longshot vive dentro del spread y lo neutraliza
  la selección adversa.

## Reproducir
python experiments/h006_g2.py; experiments/run_prices_h006r.sh; python experiments/h006_g2.py rep.
Commit 837f427. Variantes: 3.
