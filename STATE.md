# STATE

## Qué se está haciendo
- Cerradas (rechazadas): H001, H003, H006. H002 activa (forward negRisk hasta ~2026-10-20).
- Patrón: el sesgo favorito-longshot existe (+1–3 c) pero queda dentro del spread
  (taker) o lo neutraliza la selección adversa (maker). Familia "calibración en extremos"
  casi agotada.

## Hipótesis activa
- H002 — snapshots con `experiments/run_h002.sh` → data/h002/opps.csv.
- Segunda: elegir y escribir G0. Candidata: H004 (deriva cerca de la resolución) con
  precios de trades reales; o H005 (casas de apuestas) si hay fuente de odds gratuita.

## Siguiente paso exacto
1. Comprobar que run_h002.sh sigue vivo (`tail data/h002.log`); si no, relanzarlo con
   `nohup experiments/run_h002.sh &`.
2. Explorar (sin mirar resultados de PnL) si existe una fuente gratuita de odds deportivas
   históricas con timestamps (para H005). Si no, escribir G0 de H004 con ejecución por
   trades reales (Data API) y la muestra h006r para entrenamiento.
3. ~2026-10-20: evaluar H002 con la predicción G0.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 9 (H001: 3; H002: 0; H003: 3; H006: 3). Cerradas: 3.
