# STATE

## Qué se está haciendo
- Cerradas (rechazadas): H001, H003, H006. H002 activa (forward negRisk hasta ~2026-10-20).
- Patrón: el sesgo favorito-longshot existe (+1–3 c) pero queda dentro del spread
  (taker) o lo neutraliza la selección adversa (maker). Familia "calibración en extremos"
  casi agotada.

## Hipótesis activa
- H002 — snapshots con `experiments/run_h002.sh` → data/h002/opps.csv.
- H005 — G1 superado (10k mercados emparejados). Siguiente: G2.

## Siguiente paso exacto
1. Comprobar que run_h002.sh sigue vivo (`tail data/h002.log`); si no, relanzarlo con
   `nohup experiments/run_h002.sh &`.
2. H005 G1 superado (data/h005_matches.parquet, `python experiments/h005_g1.py`).
   Siguiente: G2 en entrenamiento (closedTime < 2026-04-12): trades taker en (t−1h, t],
   t = kickoff − 1h; señal θ=0.03 con PSH sin margen; PnL, IC cluster por partido, CLV vs
   PSCH y Brier PM vs Pinnacle. Script experiments/h005_g2.py (por escribir).
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
