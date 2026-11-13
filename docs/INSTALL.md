# Instalación

## Requisitos

- Python 3.11 o superior (probado con 3.13).
- Node.js 18 o superior (probado con 22) y npm.
- Sistema operativo: Linux, macOS o Windows.

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Matriz de equity preflop

El solver push/fold y el orden de manos "top X%" usan `backend/data/preflop_equity_169.json`.
El repositorio incluye una matriz generada con 20.000 muestras por pareja de clases (error estándar máximo ±0,35 %).
Para regenerarla (o aumentar la precisión):

```bash
python scripts/build_equity_matrix.py --samples 20000 --seed 7
```

Tarda unos 15-20 minutos con 20.000 muestras. Si el archivo falta, la app sigue funcionando pero el solver Nash y los percentiles de mano quedan desactivados (se avisa en la interfaz).

### Arrancar la API

```bash
uvicorn app.main:app --reload --port 8000
```

Documentación interactiva en `http://localhost:8000/docs`.

Variables de entorno:

| Variable | Uso |
|---|---|
| `ANTHROPIC_API_KEY` | Activa las explicaciones con Claude. Sin ella se usan explicaciones deterministas. |
| `POKERMIND_CLAUDE_MODEL` | Modelo a usar (por defecto `claude-opus-5-5`). |
| `POKERMIND_DB` | Ruta del archivo SQLite (por defecto `backend/data/pokermind.db`). |
| `POKERMIND_CORS` | Orígenes permitidos, separados por comas (por defecto `http://localhost:3000`). |

## Frontend

```bash
cd frontend
npm install
cp .env.example .env.local     # ajusta NEXT_PUBLIC_API_URL si el backend no está en localhost:8000
npm run dev                    # desarrollo en http://localhost:3000
npm run build && npm start     # producción
```

## Pruebas automáticas

```bash
cd backend && python -m pytest -q          # evaluador, equity, reglas del juego, API, importadores
cd frontend && npm run typecheck && npm run build
```

## Problemas habituales

- **"Matriz de equity no disponible"**: ejecuta `scripts/build_equity_matrix.py` desde `backend/`.
- **El frontend no conecta**: comprueba `NEXT_PUBLIC_API_URL` y que el backend permita el origen (`POKERMIND_CORS`).
- **Lentitud en recomendaciones postflop**: la enumeración exacta se usa hasta 500.000 evaluaciones; por encima se pasa a Monte Carlo. Puedes bajar `MAX_EXACT_EVALUATIONS` en `app/engine/equity.py`.
