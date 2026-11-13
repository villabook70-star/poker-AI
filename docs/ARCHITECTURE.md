# Arquitectura

```
backend/
  app/
    engine/        motor matemático determinista
      cards.py       cartas, baraja con semilla, 169 clases de manos
      evaluator.py   evaluación exacta 5-7 cartas (Python puro + NumPy vectorizado, mismas tablas)
      equity.py      equity por enumeración exacta o Monte Carlo (error estándar)
      ranges.py      rangos (notación estándar, pesos, top X%), carga de la matriz 169x169
      pot_odds.py    pot odds, equity mínima, EV de call/apuesta
      icm.py         ICM Malmuth-Harville
      preflop.py     rangos heurísticos de apertura/3-bet/call por posición y stack
      pushfold.py    Nash push/fold HU (juego ficticio) y estimación de open-shove BTN con ICM
    game/          reglas y simulador
      structure.py   configuración Twister (niveles, antes, premios, modo de niveles)
      engine.py      motor NLHE 2-3 jugadores: ciegas, antes, subidas mínimas, all-in cortos, botes secundarios, showdown, HU, premios
      bots.py        bots con estilos (equilibrado, tight, loose, agresivo, maníaco)
      situation.py   construye la situación del recomendador desde una partida
      session.py     sesión del simulador: snapshots, deshacer, comparar alternativas
    analysis/
      profiles.py    perfiles de rival con intervalos de Wilson y contracción bayesiana
      range_model.py estimación heurística de rangos a partir de acción, posición y perfil
      recommender.py motor de recomendación (preflop/postflop) con procedencia y confianza
    importers/     PokerStars, JSON genérico, analizador de manos importadas
    storage/db.py  SQLite (perfiles, sesiones importadas)
    ai/explain.py  explicación opcional con Claude (sin cálculos propios)
    api/           FastAPI: análisis, simulador, perfiles, importación, directo (HTTP + WS)
  scripts/build_equity_matrix.py   genera data/preflop_equity_169.json
  tests/                           pytest
frontend/   Next.js (app router) + Tailwind: mesa, panel de análisis, rejilla de rangos, páginas
```

## Flujo de una recomendación

1. Se construye una `Situation` (cartas, mesa, stacks, bote, acciones de los rivales, perfiles, premios).
2. **Preflop**
   - Bote sin abrir y stack efectivo ≤ 13 bb: heads-up → `solve_hu_push_fold` (Nash, juego restringido); botón a 3 bandas → `btn_shove_analysis` (estimación vs rangos de call asumidos + ICM).
   - Más profundo: rangos heurísticos de apertura por posición.
   - Ante un all-in: equity (exacta/Monte Carlo) vs rango estimado del agresor (rango de push Nash si está corto y es HU; si no, el modelo de rangos), pot odds, EV y ΔICM; comparación Nash cuando aplica.
   - Ante una subida normal: fold / call (aproximación) / 3-bet all-in con frecuencia de fold asumida.
3. **Postflop**: equity vs rangos estimados (sin estrechar por acciones postflop, limitación documentada), pot odds y EV de call; opciones de apuesta/all-in con frecuencia de fold tomada del perfil (o media poblacional).
4. Toda cifra lleva su etiqueta de procedencia; la confianza se deriva del margen entre alternativas y del error de estimación.

## Solver push/fold

Juego ficticio con promedio de estrategias sobre 169 clases. Pesos de eliminación de cartas exactos (`combo_counts`). Converge a explotabilidad < 0,02 bb en 400 iteraciones para stacks ≤ 20 bb. Los resultados a 10 bb (push ≈ 58 %, call ≈ 37 %) coinciden con las tablas de Nash HU ampliamente publicadas.

## Limitaciones conocidas

- Sin solver GTO postflop ni a tres bandas; el EV de las apuestas postflop es heurístico.
- Rangos postflop del rival no se estrechan por sus acciones postflop.
- La matriz de equity es una estimación Monte Carlo (±0,35 % por pareja).
- El análisis de manos importadas usa reglas simplificadas de subida mínima.
