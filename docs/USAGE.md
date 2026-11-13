# Guía de uso

## 1. Simulador (modo entrenamiento en vivo)

`/simulator`

1. Elige el estilo de los dos rivales (equilibrado, tight, loose, agresivo, maníaco), la estructura de premios (fracciones: `1.0` = el ganador se lo lleva todo; `0.8, 0.2` = dos premios) y cómo avanzan los niveles (reloj virtual de 25 s por mano o 6 manos por nivel).
2. En cada decisión verás: tus cartas, mesa, stacks (fichas y bb), posiciones, bote, acciones legales con slider de tamaño, rangos estimados de los rivales, recomendación, EV de cada alternativa, explicación y nivel de confianza.
3. Controles: **Pausar/Reanudar** (reloj), **Deshacer** (vuelve a tu última decisión con el mismo reparto), **Comparar** (repite el punto de decisión con cada alternativa usando la misma baraja; es una repetición, no un EV), **Ocultar ayuda** (para decidir sin asistencia y revisar después).
4. La estructura por defecto: 3 jugadores, 500 fichas, 10/20, niveles de 2 min, antes a partir del nivel 5. Es *configurable*: `POST /api/sim/new` acepta `config` con `levels`, `payouts`, `starting_stack`, `level_mode`, `hands_per_level`, `seconds_per_hand`, `real_time`.

## 2. Analizar una situación

`/analyze`

Describe la situación: cartas, mesa, calle, posición, stack detrás, fichas ya puestas, bote total, cantidad a pagar, ciega, ante, subidas preflop previas, jugadores vivos y premios. Para cada rival: nombre (si coincide con un perfil guardado se usan sus estadísticas), posición, stack, fichas puestas, acción preflop (`open_raise`, `limp`, `call`, `3bet`, `shove`, `call_shove`, `check`, `unknown`), all-in y fold.

La calculadora de equity acepta rangos en notación estándar (`22+, A2s+, KTs+, QJs, AJo+`), manos concretas (`QsQd`) o `top 35%`, con uno o dos rivales (`;` para separarlos).

## 3. Push/Fold

`/pushfold`

- **Heads-up**: equilibrio de Nash del juego restringido para el stack efectivo y ante elegidos; rejillas de push (SB) y call (BB), EV de cada mano.
- **Botón a 3 bandas**: estimación del EV (fichas e ICM) de un open-shove contra rangos de call asumidos. No es un equilibrio; las suposiciones se listan junto al resultado.

## 4. Perfiles de rivales

`/profiles`

Registra VPIP, PFR, 3-bet, fold a 3-bet, fold a c-bet, acciones agresivas/pasivas y notas, cada estadística con su número de oportunidades. La app muestra intervalos de confianza (Wilson 95 %) y solo asigna un estilo con al menos 30 manos y un intervalo razonablemente estrecho. Para estimar rangos usa estimaciones contraídas hacia la media poblacional (pseudo-muestra de 20 manos), lo que evita sobre-reaccionar con muestras pequeñas.

## 5. Importar partidas terminadas

`/import`

Pega historiales en formato PokerStars (Spin & Go) o en el JSON genérico (ver `IMPORT_FORMAT.md`). Para cada mano se reconstruye el estado y se analiza cada decisión tuya; las que difieren de la recomendación se marcan y, cuando ambos EV tienen la misma procedencia, se suma la pérdida de EV estimada. Las sesiones se guardan en SQLite.

Las grabaciones de vídeo no se procesan: conviértelas con una herramienta externa al JSON genérico.

## 6. Asistencia en directo (integración externa)

`/live`

- `POST /api/live/recommend` con la situación → recomendación.
- WebSocket `ws://localhost:8000/api/live/ws`: cada mensaje JSON es una situación; cada respuesta `{ok, recommendation}`.

PokerMind no captura pantallas ni lee la memoria de clientes de póker. Cualquier integración con una plataforma externa es responsabilidad del usuario y debe respetar las condiciones de la sala.

## 7. Explicaciones con IA

Con `ANTHROPIC_API_KEY` definida, el botón **Explicar con IA** envía la recomendación (con todos sus números y etiquetas de procedencia) a Claude, instruido para no inventar ni recalcular cifras. Sin clave, se muestra una explicación determinista equivalente.

## Interpretación de la confianza

- **alta**: decisión con margen claro en un cálculo exacto o de equilibrio.
- **media**: margen moderado o alguna suposición relevante (rangos estimados, ICM aproximado).
- **baja**: depende de heurísticas o de muestras pequeñas; úsala como orientación, no como verdad.
