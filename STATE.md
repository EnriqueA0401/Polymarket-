# STATE

## Qué se está haciendo
- Ciclo 1. H001 (favorito-longshot) en G1 (construcción de datos).

## Hipótesis activa
- H001 — G0 fijado en HYPOTHESES.md. Código y tests (6) en src/pmq/h001.py, tests/.

## Siguiente paso exacto
1. `experiments/run_ingest.sh` (reanudable; ventanas diarias en data/gamma; escribe TODO_OK
   en data/ingest_gamma.log al terminar). En curso: 2026-10-13 00:35 UTC iba por 2026-08.
2. `PYTHONPATH=src python -m pmq.universe` → data/universe_binary.parquet.
3. Aplicar muestreo por evento (HYPOTHESES.md H001) en fetch_prices y ejecutarlo → data/prices/h001_*.
4. Registrar hashes en data_manifest.json. Verificar G1 (timestamps, resoluciones,
   cobertura). Luego G2 solo con closedTime < 2026-04-12.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4.
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 0
