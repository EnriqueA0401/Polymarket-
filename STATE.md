# STATE

## Qué se está haciendo
- Cerradas (rechazadas): H001, H003, H004, H005, H006, H008. H002 activa (forward negRisk
  hasta ~2026-10-20).
- Patrón: con precios ejecutables PM está bien calibrado; los takers pagan el spread en
  todos los extremos; makers sufren selección adversa; copiadores pagan ~5 c.

## Hipótesis activa
- H002 — snapshots con `experiments/run_h002.sh` → data/h002/opps.csv.
- Segunda: H011 (cripto Up/Down vs Binance), nueva en la cola, prioridad alta.

## Siguiente paso exacto
1. Comprobar que run_h002.sh sigue vivo (`tail data/h002.log`); si no, relanzarlo con
   `nohup experiments/run_h002.sh &`.
2. H011: explorar (sin PnL) estructura de los mercados "Bitcoin Up or Down" (series,
   duración, regla de resolución: fuente y hora exacta del precio), disponibilidad de
   klines 1m de Binance (api.binance.com o data.binance.vision) desde este entorno.
   Luego escribir G0 (modelo de prob. justa, umbral, latencia de entrada ≥ 30 s,
   precio real de trades, comisión 0.07).
3. ~2026-10-20: evaluar H002 con la predicción G0.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 13 (H001: 3; H002: 0; H003: 3; H004: 2; H005: 1; H006: 3; H008: 1). Cerradas: 6.
