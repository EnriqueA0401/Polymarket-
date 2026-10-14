# STATE

## Qué se está haciendo
- Cerradas (rechazadas): H001, H003, H004, H005, H006, H008, H011, H012. H002 activa (forward
  negRisk hasta ~2026-10-20).
- Patrón: con precios ejecutables PM está bien calibrado y es más rápido que modelos con
  datos públicos; takers pagan spread, makers sufren selección adversa.

## Hipótesis activa
- H013 (recompensas de liquidez) — LA MÁS PROMETEDORA. Etapa 2a superada; pagos reales
  verificados (Data API /activity?type=REWARD). Etapa 2b = paper trading en 60 mercados
  desde 2026-10-14 06:46 UTC: `experiments/run_h013live.sh` (estado en
  data/h013/live/state.json, reanudable). Dura hasta ~2026-10-24 (resolución o 14 días).
- H002 — snapshots negRisk: `experiments/run_h002.sh` (evaluar ~2026-10-20).
- H010 — escaleras de fechas: `experiments/run_h010.sh` (evaluar ~2026-10-21).

## Siguiente paso exacto
1. Comprobar los 3 bucles (`tail -n1 data/h002.log`, `data/h010.log`, `data/h013live.log`);
   relanzar con `nohup experiments/run_<x>.sh &` si murieron (reinicios del contenedor).
2. Escribir experiments/h013_2b_eval.py: PnL a resolución (resultado de Gamma) + recompensas,
   IC bootstrap por mercado, rendimiento/día sobre max_capital. Revisar a mitad (~10-19) sin
   cambiar reglas.
3. Mientras: tests unitarios del paso de h013live (fills y devengo) con datos sintéticos.
4. ~2026-10-20: evaluar H002; ~2026-10-21: H010. Tras 10 cerradas (van 8): meta_review.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 17 (H001: 3; H002: 0; H003: 3; H004: 2; H005: 1; H006: 3; H008: 1; H011: 1; H012: 2; H013: 1). Cerradas: 8.
