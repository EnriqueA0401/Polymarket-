# H005 — Polymarket vs Pinnacle (fútbol) — RECHAZADA en G2

**Veredicto:** 1 h antes del partido Polymarket es tan preciso como las cuotas Pinnacle
pre-partido; las divergencias ≥ 3 c son raras y no rentables.

## Datos
- football-data.co.uk 2023/24–2026/27, 16 ligas (17,604 partidos). Emparejados 10,083
  mercados "Will X win on D?" con 0 discrepancias de resolución (reports/h005_g1.md).
- Entrenamiento (closedTime < 2026-04-12): 6,825 mercados; con cuotas Pinnacle 3,285
  (football-data no tiene PS en parte de las temporadas/ligas). Holdout NO tocado.
- Precio ejecutable = peor compra taker real en (kickoff−2h, kickoff−1h].

## Resultados (reports/h005_g2.md)
- Apuestas con edge ≥ 0.03: 72 en 60 partidos. PnL −7.26 c/acción (IC95% −16.0…+2.1).
- CLV vs Pinnacle cierre +1.86 c (61% positivo) pero no se traduce en PnL (n pequeño).
- Brier en t (n=2,808): Polymarket 0.1959 vs Pinnacle pre-partido 0.1967.

## Limitaciones
- Las cuotas PS se recogen días antes; PM a kickoff−1h tiene más información → la
  comparación favorece a PM. Un test justo necesita cuotas vivas simultáneas (forward):
  queda como H009 (baja prioridad, requiere fuente de cuotas en vivo).
- Variantes: 1. Commit 7738ab5. Reproducir: python experiments/h005_g1.py; python experiments/h005_g2.py.
