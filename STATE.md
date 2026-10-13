# STATE

## Qué se está haciendo
- H001 y H003 CERRADAS (rechazadas). H002 activa: medición forward negRisk (hasta ~2026-10-20).

## Hipótesis activa
- H002 — snapshots cada ~38 min con `experiments/run_h002.sh` → data/h002/opps.csv.
- Segunda hipótesis: elegir siguiente de la cola (H004 deriva cerca de resolución o H006
  maker en extremos). Usar SOLO precios ejecutables (trades reales/libros), ver costs.md.

## Siguiente paso exacto
1. Comprobar que run_h002.sh sigue vivo (`tail data/h002.log`); si no, relanzarlo con
   `nohup experiments/run_h002.sh &` (reinicios del contenedor lo matan).
2. H006 réplica pre-registrada (HYPOTHESES.md): precios con
   `experiments/run_prices_h006r.sh` (TODO_OK en data/fetch_prices_h006r.log), luego
   `python experiments/h006_g2.py rep` → reports/h006_rep.md. Un solo intento.
   Éxito = IC95% PnL > 0 → seguir a G3 (holdout). Fallo → rechazar H006 y escribir findings.
3. ~2026-10-20: evaluar H002 con la predicción G0.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 9 (H001: 3; H002: 0; H003: 3; H006: 3)
