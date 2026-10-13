# STATE

## Qué se está haciendo
- H001 CERRADA (rechazada G2). H002 activa: medición forward de arbitraje negRisk.

## Hipótesis activa
- H002 — G0 fijado. Snapshots cada 30 min desde 2026-10-13 ~20:00 UTC con
  `experiments/run_h002.sh` → data/h002/opps.csv (+ crudos de eventos con ret>0).
  Snapshot piloto (opps_v0.csv, 9.6k eventos): 0 arbitrajes seguros A o B.

## Siguiente paso exacto
1. Comprobar que run_h002.sh sigue vivo (`tail data/h002.log`); si no, relanzarlo
   (el contenedor se reinicia y mata procesos).
2. Tras 7 días de snapshots (≈2026-10-20): evaluar predicción G0 (≥5 eventos/semana con
   neto ≥0.5% y anualizado ≥20%, solo safe_a o B). Confirmar cada caso con los libros crudos.
3. H003 (G2 en duda): validar ejecutabilidad con trades reales de Data API: para cada
   operación de entrenamiento, ¿hubo compras de NO en [t−24h, t] y a qué precio? Recalcular
   el retorno con el precio de trade real (pesimista: peor precio de compra de NO en la
   ventana). Si el borde desaparece → rechazar por artefacto de liquidez.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 5 (H001: 3; H002: 0; H003: 2)
