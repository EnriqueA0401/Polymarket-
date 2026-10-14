# STATE

## Qué se está haciendo
- Cerradas (rechazadas): H001, H003, H005, H006, H008. H002 activa (forward negRisk
  hasta ~2026-10-20).
- Patrón: con precios ejecutables, PM está bien calibrado; sesgos dentro del spread,
  selección adversa para makers, deslizamiento ~5 c para copiadores.

## Hipótesis activa
- H002 — snapshots con `experiments/run_h002.sh` → data/h002/opps.csv.
- Segunda: elegir de la cola (H004 deriva cerca de resolución; H007/H009 solo forward).

## Siguiente paso exacto
1. Comprobar que run_h002.sh sigue vivo (`tail data/h002.log`); si no, relanzarlo con
   `nohup experiments/run_h002.sh &`.
2. Escribir G0 de H004 (deriva cerca de la resolución / mercados "casi decididos"):
   comprar el lado ≥0.97 en las últimas horas usando precio ejecutable de trades reales;
   medir rendimiento anualizado frente a riesgo de cola (resoluciones inesperadas, UMA).
   Fijar umbral, ventana y horizonte ANTES.
3. ~2026-10-20: evaluar H002 con la predicción G0.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 11 (H001: 3; H002: 0; H003: 3; H005: 1; H006: 3; H008: 1). Cerradas: 5.
