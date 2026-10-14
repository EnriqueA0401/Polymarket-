# STATE

## Qué se está haciendo
- Cerradas: H001, H003, H004, H005, H006, H008, H011, H012, H015 (rechazadas), H013 (descartada por el usuario). H002 activa (forward
  negRisk hasta ~2026-10-20).
- Patrón: con precios ejecutables PM está bien calibrado y es más rápido que modelos con
  datos públicos; takers pagan spread, makers sufren selección adversa.

## Hipótesis activa
- H002 — snapshots negRisk: `experiments/run_h002.sh` (evaluar ~2026-10-20).
- H010 — escaleras de fechas: `experiments/run_h010.sh` (evaluar ~2026-10-21).
  (Relanzados 2026-10-14 10:41 tras hueco 06:19–10:41 por reinicio.)
- H024 — G3 en HOLDOUT (una vez) en curso: `python experiments/h017_g2.py holdout` →
  reports/h024_g3.md (el script se niega a repetir si ya existe el informe).
- H014 (temperatura vs Open-Meteo) y H020 (deriva primera hora): subagentes en curso;
  archivos WIP ya subidos (src/pmq/h014.py, h020; experiments/h014_*, h020_*).

## Siguiente paso exacto
1. Comprobar bucles H002/H010 (`tail -n1 data/h002.log`, `tail -n1 data/h010.log`).
2. Leer reports/h024_g3.md y cerrar H024 (findings) según criterio pre-registrado.
3. Integrar H014 y H020 cuando terminen (revisar código/tests, informes, findings).
4. Cola restante: H019 (UMA, baja prioridad), H021 (combinatorio, coste alto), H023 (lead-lag
   Kalshi, prior bajo), H007/H009 (solo forward). Si fallan H014/H020/H024 → meta-revisión
   anticipada sobre si existe borde con datos públicos y latencia de minutos.
5. ~2026-10-20: evaluar H002; ~2026-10-21: H010.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 21 (H001: 3; H002: 0; H003: 3; H004: 2; H005: 1; H006: 3; H008: 1; H011: 1; H012: 2; H013: 1; H015: 1; H016: 1; H017: 1; H018: 1). Cerradas: 13 (+H022 descartada sin prueba).
