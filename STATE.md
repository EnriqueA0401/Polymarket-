# STATE

## Qué se está haciendo
- Cerradas (rechazadas): H001, H003, H004, H005, H006, H008, H011. H002 activa (forward
  negRisk hasta ~2026-10-20).
- Patrón: con precios ejecutables PM está bien calibrado y es más rápido que modelos con
  datos públicos; takers pagan spread, makers sufren selección adversa.

## Hipótesis activa
- H002 — snapshots negRisk cada ~38 min: `experiments/run_h002.sh` → data/h002/opps.csv.
- H010 — escaleras de fechas, snapshots horarios desde 2026-10-14 04:55 UTC:
  `experiments/run_h010.sh` → data/h010/opps.csv. Piloto: 1,775 pares, 0 positivos.

## Siguiente paso exacto
1. Comprobar que ambos bucles siguen vivos (`tail -1 data/h002.log data/h010.log`); si no,
   relanzar con `nohup experiments/run_h002.sh &` y `nohup experiments/run_h010.sh &`
   (los reinicios del contenedor los matan).
2. Mientras miden: proponer nuevas hipótesis (cola casi vacía): p.ej. H012 reacción a
   noticias en mercados políticos (sobre/infrarreacción tras saltos ≥10 c, con trades
   reales), H013 programa de recompensas de liquidez (¿rewards > selección adversa?).
   Escribir G0 de la más barata.
3. ~2026-10-20: evaluar H002; ~2026-10-21: evaluar H010 (predicciones G0).
4. Tras 10 hipótesis cerradas (van 7): reports/meta_review.md.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 14 (H001: 3; H002: 0; H003: 3; H004: 2; H005: 1; H006: 3; H008: 1; H011: 1). Cerradas: 7.
