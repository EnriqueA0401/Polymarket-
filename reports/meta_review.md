# Meta-revisión nº 1 (2026-10-14, tras 10 hipótesis cerradas)

Contador global de pruebas: 18. Holdout intacto (ninguna hipótesis llegó a G3).

## Resultado agregado
| id | familia | veredicto | causa principal |
|---|---|---|---|
| H001 | calibración (extremos, taker) | rechazada G2 | borde bruto ~1 c < coste real ~2 c |
| H003 | calibración (sobreprecio Yes) | rechazada G1/G2 | precios históricos no ejecutables |
| H004 | temporal (favoritos cerca del cierre) | rechazada G2 | acierto < precio pagado |
| H005 | externa (Pinnacle, fútbol) | rechazada G2 | PM tan preciso como Pinnacle pre-partido |
| H006 | microestructura (maker extremos) | rechazada G2 + réplica | selección adversa anula el sesgo |
| H008 | flujo de wallets (copiar top) | rechazada G2 | habilidad poco persistente, ~5 c de deslizamiento |
| H011 | externa (cripto Up/Down vs Binance) | rechazada G2 | PM más rápido que spot público a 30–90 s |
| H012 | temporal (saltos) | rechazada G2 | spreads ~20 c donde hay saltos |
| H013 | microestructura (recompensas) | descartada | probada en real por el usuario sin buenos resultados |
| H015 | temporal (post-evento) | rechazada G4/G6 | sin vendedores <0.995 tras el partido |

## Qué familias están agotadas
1. **Calibración simple (favorito-longshot, Yes, favoritos cercanos al cierre):** AGOTADA.
   El sesgo existe pero mide 1–3 c y vive dentro del spread; como taker se paga, como maker lo
   anula la selección adversa.
2. **Reacción/dinámica de precio con datos de PM únicamente (saltos, deriva):** AGOTADA.
   En mercados ilíquidos el coste de entrada es ~10 c; en líquidos no hay patrón.
3. **Seguir flujo (wallets top):** prácticamente agotada; queda solo el caso de muy baja
   latencia, fuera de alcance.
4. **Fuentes externas "rápidas" (spot cripto, cuotas pre-partido):** PM ya incorpora la
   información pública más rápido que nuestra latencia o igual de bien.
5. **Post-evento / casi decididos:** agotada; los bots cierran la brecha al instante.

## Lecciones metodológicas
- prices-history NO es ejecutable fuera de mercados líquidos; toda prueba usa trades reales
  (peor precio taker) o libros vivos. Este filtro ha cambiado el signo de dos hipótesis.
- Los resultados "demasiado buenos" fueron artefactos o incompletos (H003, H013): la regla
  de asumir un bug funcionó.
- Las réplicas pre-registradas en muestras disjuntas (H006) evitan falsos positivos de G2.

## ¿Cambiar de enfoque? Sí
Dejar de buscar sesgos en el precio de PM y concentrarse en:
1. **Información externa lenta pero de alta calidad** en mercados minoristas con poca atención
   de bots, donde la latencia no importa (horas/días): meteorología (H014), datos macro con
   nowcasts (H022), barreras cripto con modelo de opciones (H016).
2. **Estructura/contratos mal valorados** donde la valoración requiere un modelo (barreras,
   escaleras de fechas H010, combinatorio H021) y no simple calibración.
3. **Prima de riesgo a largo plazo** (H017 carry en NO) frente al coste de oportunidad.
4. Mantener H002/H010 en forward como control de arbitraje puro.

Criterio de parada de la familia: si H014, H016 y H017 fallan, la próxima meta-revisión debe
plantear que no existe borde explotable para < 1,000 USD con datos públicos y latencia de
minutos, y documentarlo como resultado principal.

---

# Meta-revisión nº 2 (2026-10-14, anticipada por la regla de parada; 17 cerradas, 26 pruebas)

Se cumplió la condición de la nº 1: fallaron H014 (meteorología), H016 (barreras cripto) y
H017/H024 (carry a largo plazo), además de H015, H018, H020, H025.

## Conclusión principal (resultado negativo documentado)
Con datos públicos gratuitos, latencia de minutos y precios realmente ejecutables, NO se ha
encontrado un borde explotable para < 1,000 USD en Polymarket. Patrones repetidos:
- El precio de PM bate a modelos externos razonables (Pinnacle, Binance, Open-Meteo,
  opciones/volatilidad): Brier del mercado ≤ Brier del modelo en H005, H011, H014, H016.
- Los sesgos que existen (favorito-longshot a 24h–90d, ~1–2 c/acción) quedan dentro del spread,
  los anula la selección adversa o rinden por debajo del tipo libre de riesgo (H001, H006, H017/H024).
- Lo "post-evento" y las ventanas de apertura ya las cierran bots (H015, H020).
- Los resultados aparentes desaparecen con métricas correctas (anualización de cartera,
  censura, precios ejecutables).

## Qué queda con prior razonable
1. Medición forward en curso: H002 (negRisk) y H010 (escaleras de fechas) — arbitraje puro.
2. Forward/paper trading de subgrupos post hoc (H026) — solo como G7, sin holdout disponible.
3. Familias no probadas y caras: arbitraje combinatorio (H021), lead-lag Kalshi (H023),
   UMA (H019, prior rebajado). Requieren infraestructura o latencia fuera de alcance.

## Recomendación
- Mantener H002/H010 hasta su evaluación (20–21/10) y lanzar H026 en paper trading barato.
- No abrir más hipótesis de calibración ni de "modelo externo vs precio" sin una fuente de
  información claramente privilegiada (no pública o más lenta de incorporar).
- Si H002, H010 y H026 fallan, cerrar el proyecto con el informe final de resultado negativo.
