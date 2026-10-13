# STATE

## Qué se está haciendo
- Ciclo 1. H001 (favorito-longshot) en G1 (construcción de datos).

## Hipótesis activa
- H001 — G0 fijado en HYPOTHESES.md. Código y tests (6) en src/pmq/h001.py, tests/.

## Siguiente paso exacto
1. Ingesta Gamma COMPLETA (4384 ventanas diarias, 2026-10-13 18:10 UTC).
2. `PYTHONPATH=src python -m pmq.universe` → data/universe_binary.parquet (en curso).
3. Registrar hashes en data_manifest.json; aplicar muestreo por evento (H001) en
   fetch_prices y ejecutarlo → data/prices/h001_*.
4. Verificación G1 (timestamps, resoluciones, cobertura). Luego G2 con closedTime < 2026-04-12.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 0
