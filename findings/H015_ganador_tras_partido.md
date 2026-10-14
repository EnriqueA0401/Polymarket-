# H015 — Comprar al ganador tras el partido — RECHAZADA (frecuencia/capacidad)

**Veredicto:** tras el final, el ganador ya cotiza ≥ 0.995 casi siempre; casi no hay
vendedores. 6 oportunidades en 6,821 mercados de entrenamiento: inviable.

## Resultados (reports/h015_g2.md; holdout NO tocado)
- Mercados abiertos en kickoff+3h: 6,821. Con alguna compra real del ganador en (t, t+2h]:
  250. Con precio ≤ 0.995: 6 (6 partidos).
- En esos 6: PnL +5.5 c/acción (IC95% +0.9…+14.4), ningún fallo de resolución. Pero n=6 ≪ 150
  (G4) y la mediana de compras disponibles por mercado es 0 → capacidad ≈ nula.
- El anualizado astronómico es un artefacto de horizontes de horas; no significa nada.

## Lectura
Los bots cierran la brecha post-evento al instante (≥ 0.995). Pierde muy poca gente aquí.
H019 (ventana UMA) es la generalización; prior rebajado por este resultado.

Commit 08dbc30. Variantes: 1. Reproducir: python experiments/h015_g2.py.
