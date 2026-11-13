"""PokerMind AI - FastAPI application entry point."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import routes_analysis, routes_import, routes_live, routes_profiles, routes_sim
from .engine.ranges import load_equity_data



@asynccontextmanager
async def lifespan(_: FastAPI):
    load_equity_data()  # warm the preflop matrix cache
    yield


app = FastAPI(title="PokerMind AI", version="0.1.0", lifespan=lifespan,
              description="Motor determinista de análisis y entrenamiento para Twister Poker (3-max Spin & Go).")

origins = os.environ.get("POKERMIND_CORS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(routes_analysis.router)
app.include_router(routes_sim.router)
app.include_router(routes_profiles.router)
app.include_router(routes_import.router)
app.include_router(routes_live.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "equity_matrix": bool(load_equity_data()), "version": app.version}
