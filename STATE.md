# STATE

## Qué se está haciendo
- H001 CERRADA (rechazada G2: borde bruto ≈1 c < coste real ≈2 c). Ver findings/.
- Siguiente hipótesis por prioridad: H002 (suma negRisk ≠ 1) — barata con libros vivos.

## Hipótesis activa
- H002 — pendiente de escribir protocolo G0.

## Siguiente paso exacto
1. Escribir G0 de H002 en HYPOTHESES.md (antes de ver datos): en eventos negRisk abiertos,
   suma de best asks YES < 1 − costes (comprar todos) o suma de best bids > 1 (vender/NO).
   Necesita libros vivos simultáneos; registrar snapshots periódicos (no hay historial).
2. Script experiments/h002_snapshot.py: snapshot de todos los eventos negRisk abiertos.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 3 (H001: 3)
