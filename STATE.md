# STATE

## Qué se está haciendo
- Cerradas: H001, H003, H004, H005, H006, H008, H011, H012, H015 (rechazadas), H013 (descartada por el usuario). H002 activa (forward
  negRisk hasta ~2026-10-20).
- Patrón: con precios ejecutables PM está bien calibrado y es más rápido que modelos con
  datos públicos; takers pagan spread, makers sufren selección adversa.

## Hipótesis activa
- H002 — snapshots negRisk: `experiments/run_h002.sh` (evaluar ~2026-10-20).
- H010 — escaleras de fechas: `experiments/run_h010.sh` (evaluar ~2026-10-21).
- H014 — temperatura vs pronóstico Open-Meteo: G0 escrito; G1/G2 delegados a un subagente
  (archivos src/pmq/h014.py, experiments/h014_g*.py, reports/h014_g*.md).
- H015 RECHAZADA (6 oportunidades en 6,821 mercados).
- H016 (barreras cripto) delegada a subagente. H017 RECHAZADA (anualizado 7.9%, IC incluye <4%;
  es el borde por acción más claro hasta ahora: +1.8 c). H018 (menciones) en curso: experiments/h018_g2.py.
- Un subagente investiga hipótesis nuevas (literatura/foros) para la cola.

## Siguiente paso exacto
1. Comprobar bucles H002/H010 (`tail -n1 data/h002.log`, `tail -n1 data/h010.log`).
2. Integrar resultados de H014 (revisar código, tests, informe; commit) y H015.
3. Añadir a HYPOTHESES.md las mejores ideas del subagente de investigación (G0 antes de datos).
4. Meta-revisión nº1 hecha (reports/meta_review.md). Próxima tras 20 cerradas.
5. ~2026-10-20: evaluar H002; ~2026-10-21: H010.

## Bloqueos / limitaciones
- prices-history en mercados resueltos: interval=max solo da diario; ventanas ≤14d con
  startTs/endTs dan horario. No hay historial de libro → coste pesimista fijo 0.02/acción.
- Gamma devuelve 403 (Cloudflare) con 8 hilos; usar 4. Algunos cursores dan 403
  determinista: ingest_gamma parte la ventana en mitades (resuelto).
- Volumen: ~20k mercados cerrados/día en 2026.
- Mercados sin endDate no se capturan por ventanas de endDate (cuantificar).

## Contador global de pruebas
- 19 (H001: 3; H002: 0; H003: 3; H004: 2; H005: 1; H006: 3; H008: 1; H011: 1; H012: 2; H013: 1; H015: 1; H017: 1). Cerradas: 11.
