# STATE

**INVESTIGACIÓN DETENIDA por el usuario (2026-10-15 03:00 UTC).** Subagentes H038/H042 parados
(H038 y H042 con código a medias, sin resultados), bucles forward detenidos, tarea programada
desactivada y hook SessionStart retirado. Para reanudar: reactivar todo y ejecutar
`experiments/ensure_loops.sh`.

## Qué se está haciendo
- Cerradas: H001, H003, H004, H005, H006, H008, H011, H012, H015 (rechazadas), H013 (descartada por el usuario). H002 activa (forward
  negRisk hasta ~2026-10-20).
- Patrón: con precios ejecutables PM está bien calibrado y es más rápido que modelos con
  datos públicos; takers pagan spread, makers sufren selección adversa.

## Hipótesis activa
- ALCANCE AMPLIADO (usuario, 14/10): opciones binarias (ver CLAUDE.md). En curso: H038 [BIN]
  calibración Kalshi (subagente), H040 [BIN] RECHAZADA (acierto máx. 51.1% < 55.6%).
- H039 [BIN] arbitraje Kalshi↔PM: G2 histórico +5.75 c en 422 partidos pero reglas distintas
  (aplazado/cancelado) y bots ya presentes. Forward con libros reales desde 15/10 02:40
  (data/h039/live.csv); evaluar ~2026-10-22.
- H002 — snapshots negRisk (evaluar ~2026-10-20).
- H010 — escaleras de fechas (evaluar ~2026-10-21).
- H026 — paper trading carry NO a ~90 d en mercados NO negRisk: registro cada 6 h desde
  2026-10-14 15:42 (data/h026/signals.csv; 104 señales iniciales en 29 eventos). Resolución
  ~enero 2027; evaluar con rentabilidad de CARTERA y censura por evento.
- Meta-revisión nº2: sin borde explotable con datos públicos tras 17 cerradas.
- H027 RECHAZADA (PM bate al nowcast METAR). H028 RECHAZADA (PM bate a la tasa base).
  H023 RECHAZADA (seguimiento PM ~0.5 c < costes). H032 RECHAZADA (PM bate al modelo; n=55).
- H034 RECHAZADA (props esports 50-50: no identificable en t). H036 (conversión NO→YES) medida
  forward en snapshots de H002 (data/h002/opps_conv.csv).
- H037 (monotonía en escaleras de strikes): snapshots horarios desde 2026-10-14 22:10
  (`experiments/run_h037.sh`); piloto tras corregir 2 bugs de parseo: 3 pares ≥0.5% (máx 1.4%).
  Evaluar ~2026-10-21. H035 RECHAZADA (lado propuesto gana 35%). H041 RECHAZADA (−5.2 c; holdout intacto).
- H033 (presidencia ≤ nominación 2028): snapshots cada 6 h (`experiments/run_h033.sh`). Piloto:
  121 pares, máximo +0.29% (anualizado 0.14%) → coherente; evaluar ~2026-11-11. H029–H032 en cola solo forward (n < 150 en entrenamiento).

## Siguiente paso exacto
1. SIEMPRE al empezar: `experiments/ensure_loops.sh` (relanza H002/H010/H026/H033/H037/H039 si murieron;
   también lo ejecuta el hook SessionStart de .claude/settings.json).
   Parcial 14/10 20:45: H002 21 snapshots, 5 eventos A seguros ≥0.5% pero 0 con anualizado ≥20%;
   H010 7 snapshots, 0 pares ≥0.5%.
2. Evaluación H026: `python experiments/h026_eval.py` → reports/h026_g7.md (útil cuando haya resoluciones).
3. ~2026-10-20: evaluar H002; ~2026-10-21: H010. Si fallan y H026 no avanza → informe final.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 36 (H001: 3; H002: 0; H003: 3; H004: 2; H005: 1; H006: 3; H008: 1; H011: 1; H012: 2; H013: 1; H015: 1; H016: 1; H017: 1; H018: 1; H020: 2; H024: 1; H025: 1; H014: 1; H027: 1; H028: 1; H023: 1; H032: 1; H034: 1; H035: 1; H040: 2; H041: 1; H039: 1). Cerradas: 25 (+H022 descartada sin prueba).
