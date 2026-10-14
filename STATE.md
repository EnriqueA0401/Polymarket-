# STATE

## Qué se está haciendo
- Cerradas (rechazadas): H001, H003, H005, H006. H002 activa (forward negRisk hasta ~2026-10-20).
- Patrón: precios de PM bien calibrados una vez se usan precios ejecutables; los sesgos
  de calibración quedan dentro del spread o los anula la selección adversa.

## Hipótesis activa
- H002 — snapshots con `experiments/run_h002.sh` → data/h002/opps.csv.
- Segunda: elegir de la cola. Candidatas: H004 (deriva cerca de resolución) o una nueva de
  flujo de wallets (seguir wallets rentables, validación fuera de muestra) — familia sin explorar.

## Siguiente paso exacto
1. Comprobar que run_h002.sh sigue vivo (`tail data/h002.log`); si no, relanzarlo con
   `nohup experiments/run_h002.sh &`.
2. Escribir G0 de H008 (flujo de wallets): con Data API, PnL realizado por wallet en un
   periodo de formación; seguir a las top-k wallets en un periodo posterior (entrada al
   peor precio real tras su trade, con retraso ≥ 1 min). Fijar k, periodos y retraso ANTES.
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
