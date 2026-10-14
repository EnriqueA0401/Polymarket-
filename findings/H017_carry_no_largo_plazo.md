# H017 — Carry en NO de eventos improbables a 90 días — RECHAZADA (criterio pre-registrado)

**Veredicto:** el sesgo existe y es significativo por acción (+1.8 c), pero el rendimiento
anualizado (7.9%) no supera con confianza el 4% libre de riesgo: IC95% −5.8%…+17.9%.
Es el resultado más cercano a un borde hasta ahora.

## Datos (entrenamiento; holdout NO tocado; reports/h017_g2.md)
- 6,041 mercados con duración ≥120 d abiertos en end−90d (universo completo, enmienda previa
  a datos). Señal 0.02 ≤ p ≤ 0.10: 1,702; con compra real de NO en (t−3d, t]: 936 (567 eventos).
- Precio medio NO 0.959; YES ocurrió en 2.0% (precio implícito ~4.1%).
- PnL +1.79 c/acción (IC95% +0.86…+2.62). Anualizado medio 7.87% (IC −5.81%…+17.93%),
  días medios 81. Criterio (media >6% e IC inferior >4%): NO cumple.

## Lectura
A 90 días el sesgo favorito-longshot es mayor que a 24h (2.0% real vs 4.1% implícito) y supera
el coste de entrada, pero inmoviliza capital ~3 meses: rinde como una letra del Tesoro con
riesgo de cola. Sin holding rewards (no contados por pesimismo) no compensa.
Posible extensión (nueva hipótesis, no variante a posteriori): incluir holding rewards
documentadas por mercado y carteras diversificadas por tema.

Commit 5ea0a15. Variantes: 1. Reproducir: python experiments/h017_g2.py.
