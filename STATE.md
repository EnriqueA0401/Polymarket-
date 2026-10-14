# STATE

## Qué se está haciendo
- Cerradas (rechazadas): H001, H003, H005, H006. H002 activa (forward negRisk hasta ~2026-10-20).
- Patrón: precios de PM bien calibrados una vez se usan precios ejecutables; los sesgos
  de calibración quedan dentro del spread o los anula la selección adversa.

## Hipótesis activa
- H002 — snapshots con `experiments/run_h002.sh` → data/h002/opps.csv.
- H008 — seguir wallets rentables. G0 escrito, G2 ejecutándose.

## Siguiente paso exacto
1. Comprobar que run_h002.sh sigue vivo (`tail data/h002.log`); si no, relanzarlo con
   `nohup experiments/run_h002.sh &`.
2. H008 (G0 escrito): `python experiments/h008.py` (cachés reanudables en data/trades_h008_*)
   → reports/h008_g2.md. En curso desde 2026-10-14 ~01:30 UTC (~26.7k mercados + copias).
3. ~2026-10-20: evaluar H002 con la predicción G0.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 10 (H001: 3; H002: 0; H003: 3; H005: 1; H006: 3). Cerradas: 4.
