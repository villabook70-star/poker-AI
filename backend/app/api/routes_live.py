"""Live-assist integration for external platforms.

PokerMind does not scrape or read any poker client (that usually violates
the operator's terms of service). Instead it exposes a neutral interface:
external tools (manual entry, a user-written HUD bridge, an OCR adapter...)
send the current situation and receive the deterministic recommendation.

* ``POST /api/live/recommend`` - one-shot request/response.
* ``WS   /api/live/ws``        - persistent WebSocket; each JSON message is a
  situation (same schema as POST), each reply a recommendation.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from ..analysis.recommender import recommend
from . import schemas
from .routes_analysis import situation_from_schema

router = APIRouter(prefix="/api/live", tags=["live"])


@router.post("/recommend")
def live_recommend(s: schemas.SituationIn):
    try:
        return recommend(situation_from_schema(s)).to_dict()
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.websocket("/ws")
async def live_ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                s = schemas.SituationIn.model_validate(json.loads(raw))
                rec = recommend(situation_from_schema(s)).to_dict()
                await ws.send_text(json.dumps({"ok": True, "recommendation": rec}, ensure_ascii=False))
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                await ws.send_text(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
    except WebSocketDisconnect:
        return
