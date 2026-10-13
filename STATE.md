# STATE

## Qué se está haciendo
- Ciclo 1. H001 (favorito-longshot) en G1 (construcción de datos).

## Hipótesis activa
- H001 — G0 fijado en HYPOTHESES.md. Código y tests (6) en src/pmq/h001.py, tests/.

## Siguiente paso exacto
1. Universo listo (4.1M binarios, reports/h001_g1_universe.md, hashes en data_manifest.json).
2. Precios muestra H001 (107k mercados): `experiments/run_prices.sh` (reanudable,
   escribe TODO_OK en data/fetch_prices.log). En curso 2026-10-13 18:50 UTC, ~1h.
3. Al terminar: `python experiments/h001_g2.py` → reports/h001_g2.md (solo entrenamiento).
   Sumar 2 al contador global (h=24h y h=7d).
4. Revisar riesgo G1: endDate editado ex post (posible lookahead en t=end−h).

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 0
