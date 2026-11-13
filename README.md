# PokerMind AI

Aplicación de entrenamiento y análisis para **Twister Poker** (Spin & Go 3-max, Texas Hold'em No Limit).

- **Motor determinista** en Python: evaluación exacta de manos, equity por enumeración o Monte Carlo (con error estándar), pot odds, ICM, rangos, equilibrio de Nash push/fold heads-up calculado localmente, estimaciones de open-shove a 3 bandas, recomendador con nivel de confianza.
- **Simulador interactivo** de 3 jugadores con bots de distintos estilos, niveles de ciegas de 2 minutos (reloj virtual o real), antes, transición automática a heads-up, estructura de premios configurable, pausa, deshacer y comparación de alternativas con el mismo reparto.
- **Perfilado de rivales** (VPIP, PFR, 3-bet, folds, agresividad, tamaños de apuesta) con intervalos de confianza según la muestra; nunca asigna un estilo con pocas manos.
- **Importación de partidas** (historiales PokerStars o JSON genérico) con reconstrucción mano a mano y análisis de errores.
- **Asistencia en directo** mediante API HTTP y WebSocket neutrales para herramientas externas.
- **Explicaciones opcionales con Claude**: el modelo solo redacta a partir de los números del motor; nunca calcula ni inventa porcentajes.
- Interfaz **Next.js + React + TypeScript + Tailwind**, oscura y adaptada a móvil.

## Procedencia de cada número

| Etiqueta | Significado |
|---|---|
| `exact` | Enumeración completa o aritmética (evaluación de manos, equity en flop/turn/river, pot odds, EV de un all-in dada la equity, ICM dado el modelo). |
| `monte_carlo` | Estimación estadística insesgada con número de muestras y error estándar declarados. |
| `nash` | Equilibrio de Nash del **juego restringido** push/fold heads-up (SB: all-in o fold; BB: call o fold) calculado por juego ficticio sobre la matriz de equity 169×169. |
| `heuristic` | Reglas prácticas (rangos de apertura por posición, rangos estimados del rival, frecuencias de fold asumidas). **Nunca se presentan como óptimas.** |

La aplicación **no incluye soluciones GTO postflop ni de 3 jugadores**. Cuando no hay datos verificables, el campo `gto_comparison.available` es `false` y se indica el motivo.

## Inicio rápido

```bash
# Backend (Python 3.11+)
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/build_equity_matrix.py                  # ~15-20 min, una sola vez (ya incluido en data/)
uvicorn app.main:app --reload --port 8000

# Frontend (Node 18+)
cd frontend
npm install
npm run dev                                            # http://localhost:3000
```

Variables opcionales: `ANTHROPIC_API_KEY` (explicaciones con Claude), `POKERMIND_DB` (ruta SQLite), `NEXT_PUBLIC_API_URL` (URL del backend).

Documentación completa: [docs/INSTALL.md](docs/INSTALL.md), [docs/USAGE.md](docs/USAGE.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/IMPORT_FORMAT.md](docs/IMPORT_FORMAT.md).

## Pruebas

```bash
cd backend && python -m pytest -q
cd frontend && npm run typecheck && npm run build
```

## Aviso

Esta herramienta es para estudio y entrenamiento. No lee ni captura la pantalla de ningún cliente de póker; el uso de asistencia en tiempo real sobre plataformas de terceros puede estar prohibido por sus condiciones de uso. Comprueba las normas de tu sala antes de integrar nada.
