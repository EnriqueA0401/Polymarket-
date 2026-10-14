# H032 — Número de posts semanales con contador XTracker — RECHAZADA en G2 (G4 inviable)

**Veredicto:** a mitad de semana el precio de PM ya incorpora el recuento y el ritmo de la
cuenta mejor que un modelo empírico; las apuestas pierden. Además solo hay 55 eventos usables.

## G1 (reports/h032_g1.md)
270 eventos de entrenamiento; historia XTracker desde nov-2025 (Elon) y ene–mar 2026 (resto).
Concordancia recuento vs tramo resuelto 100% salvo Trump (88%, excluido). Usables: 55
(Elon 38, Tate 8, White House 6, Cruz 3) → G4 (≥150) imposible.

## G2 (reports/h032_g2.md; holdout NO tocado)
188 apuestas en 49 eventos: PnL −5.37 c (IC95% −10.37…−0.25); costes×2 −7.33 c; sin top-5
−9.61 c. Brier modelo 0.0764 vs precio 0.0631 (modelo significativamente peor).

Sustituciones: 8 bloques contiguos de longitud R terminando en t; series de 48 h y mensuales
excluidas; capital-días hasta closedTime. Implementación: subagente; 109 tests.
Commit 4ae5db7. Variantes: 1.
