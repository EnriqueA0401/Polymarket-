# STATE

## Qué se está haciendo
- Ciclo 1. H001 (favorito-longshot) en G1 (construcción de datos).

## Hipótesis activa
- H001 — G0 fijado en HYPOTHESES.md. Código y tests (6) en src/pmq/h001.py, tests/.

## Siguiente paso exacto
1. `PYTHONPATH=src python -m pmq.ingest_gamma` (reanudable; ventanas mensuales en data/gamma).
2. `PYTHONPATH=src python -m pmq.universe` → data/universe_binary.parquet.
3. `PYTHONPATH=src python -m pmq.fetch_prices` (reanudable) → data/prices/h001_*.
4. Registrar hashes en data_manifest.json. Verificar G1 (timestamps, resoluciones,
   cobertura). Luego G2 solo con closedTime < 2026-04-12.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 0
