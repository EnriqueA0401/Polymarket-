# STATE

## Qué se está haciendo
- Cerradas: H001, H003, H004, H005, H006, H008, H011, H012, H015 (rechazadas), H013 (descartada por el usuario). H002 activa (forward
  negRisk hasta ~2026-10-20).
- Patrón: con precios ejecutables PM está bien calibrado y es más rápido que modelos con
  datos públicos; takers pagan spread, makers sufren selección adversa.

## Hipótesis activa
- H002 — snapshots negRisk: `experiments/run_h002.sh` (evaluar ~2026-10-20).
- H010 — escaleras de fechas: `experiments/run_h010.sh` (evaluar ~2026-10-21).
- Meta-revisión nº2 (reports/meta_review.md): sin borde explotable con datos públicos y
  latencia de minutos tras 17 hipótesis cerradas. Quedan forward: H002, H010, H026.

## Siguiente paso exacto
1. Comprobar bucles H002/H010 (`tail -n1 data/h002.log`, `tail -n1 data/h010.log`).
2. H026: escribir G0 de paper trading forward (mercados NO negRisk, duración ≥120 d, YES
   0.02–0.10 a ~90 d: registrar señales diarias con precio ejecutable del libro; rentabilidad
   de cartera; criterio G7: ≥ 50 mercados resueltos o 4 semanas — resolución tarda ~90 d,
   así que es un test de largo plazo).
3. ~2026-10-20: evaluar H002; ~2026-10-21: H010. Si fallan → informe final negativo.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 26 (H001: 3; H002: 0; H003: 3; H004: 2; H005: 1; H006: 3; H008: 1; H011: 1; H012: 2; H013: 1; H015: 1; H016: 1; H017: 1; H018: 1; H020: 2; H024: 1; H025: 1; H014: 1). Cerradas: 17 (+H022 descartada sin prueba).
