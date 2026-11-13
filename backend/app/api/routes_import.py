from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..importers.analyzer import analyze_hand, update_profiles_from_hands
from ..importers.generic_json import parse_generic_json
from ..importers.pokerstars import parse_pokerstars
from ..storage.db import Database
from . import schemas

router = APIRouter(prefix="/api/import", tags=["import"])
_db: Database | None = None


def db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


@router.post("")
def import_hands(req: schemas.ImportRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "Texto vacío")
    fmt = req.format
    if fmt == "auto":
        fmt = "json" if text.startswith("{") or text.startswith("[") else "pokerstars"
    try:
        hands, warnings = parse_generic_json(text) if fmt == "json" else parse_pokerstars(text, req.hero)
    except ValueError as exc:
        raise HTTPException(400, f"No se pudo interpretar el historial: {exc}")
    if not hands:
        raise HTTPException(400, "No se reconoció ninguna mano. " + " ".join(warnings))
    profiles = db().all_profiles()
    if req.update_profiles:
        profiles = update_profiles_from_hands(hands, profiles)
        for p in profiles.values():
            db().save_profile(p)
    analyses = [analyze_hand(h, profiles) for h in hands]
    decisions = sum(len(a["decisions"]) for a in analyses)
    mistakes = sum(a.get("mistakes", 0) for a in analyses)
    ev_loss = round(sum(a.get("total_ev_loss_bb", 0) for a in analyses), 2)
    summary = {"hands": len(hands), "decisions": decisions, "mistakes": mistakes, "ev_loss_bb_estimate": ev_loss,
               "warnings": warnings, "format": fmt,
               "note": "La pérdida de EV solo se suma cuando ambas acciones tienen EV comparable; es una estimación."}
    sid = db().create_session(req.name, fmt, [h.to_dict() for h in hands], analyses, summary)
    return {"session_id": sid, "summary": summary, "hands": analyses}


@router.get("/sessions")
def sessions():
    return db().list_sessions()


@router.get("/sessions/{sid}")
def session(sid: int):
    s = db().get_session(sid)
    if not s:
        raise HTTPException(404, "Sesión no encontrada")
    return s


@router.delete("/sessions/{sid}")
def delete_session(sid: int):
    if not db().delete_session(sid):
        raise HTTPException(404, "Sesión no encontrada")
    return {"ok": True}
