# STATE

## Qué se está haciendo
- Cerradas: H001, H003, H004, H005, H006, H008, H011, H012 (rechazadas), H013 (descartada por el usuario). H002 activa (forward
  negRisk hasta ~2026-10-20).
- Patrón: con precios ejecutables PM está bien calibrado y es más rápido que modelos con
  datos públicos; takers pagan spread, makers sufren selección adversa.

## Hipótesis activa
- H002 — snapshots negRisk: `experiments/run_h002.sh` (evaluar ~2026-10-20).
- H010 — escaleras de fechas: `experiments/run_h010.sh` (evaluar ~2026-10-21).
- H013 DESCARTADA por el usuario (probada en real sin buenos resultados). No reabrir.

## Siguiente paso exacto
1. Comprobar los 2 bucles (`tail -n1 data/h002.log`, `tail -n1 data/h010.log`); relanzar
   con `nohup experiments/run_<x>.sh &` si murieron.
2. Cola vacía salvo forward: proponer y escribir G0 de una hipótesis nueva de familia no
   explorada (p. ej. mercados de resolución por datos oficiales —economía, clima— frente a
   pronósticos públicos; o patrones intradía/semanales con precios ejecutables).
3. Tras 10 hipótesis cerradas (van 9): reports/meta_review.md.
4. ~2026-10-20: evaluar H002; ~2026-10-21: H010.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 17 (H001: 3; H002: 0; H003: 3; H004: 2; H005: 1; H006: 3; H008: 1; H011: 1; H012: 2; H013: 1). Cerradas: 9.
