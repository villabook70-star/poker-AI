from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, HTTPException

from ..game.bots import BOT_STYLES
from ..game.engine import IllegalAction
from ..game.session import SimSession
from ..game.structure import TwisterConfig, default_twister_structure
from ..storage.db import Database
from . import schemas

router = APIRouter(prefix="/api/sim", tags=["simulator"])
SESSIONS: Dict[str, SimSession] = {}
MAX_SESSIONS = 50
_db: Database | None = None


def db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def get(sid: str) -> SimSession:
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Sesión no encontrada")
    return s


@router.get("/structure/default")
def structure_default():
    return default_twister_structure().to_dict()


@router.get("/bot-styles")
def bot_styles():
    return {k: v["label"] for k, v in BOT_STYLES.items()}


@router.post("/new")
def new_sim(req: schemas.NewSimRequest):
    try:
        cfg = TwisterConfig.from_dict(req.config) if req.config else default_twister_structure()
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, f"Configuración inválida: {exc}")
    if len(SESSIONS) >= MAX_SESSIONS:
        SESSIONS.pop(next(iter(SESSIONS)))
    sess = SimSession.create(cfg, req.hero_name, req.bot_profiles, req.seed)
    sess.profiles = db().all_profiles()
    SESSIONS[sess.id] = sess
    sess.run_until_hero()
    return sess.state()


@router.get("/{sid}")
def state(sid: str):
    return get(sid).state()


@router.get("/{sid}/recommend")
def recommend_sim(sid: str):
    s = get(sid)
    rec = s.recommendation()
    if rec is None:
        raise HTTPException(409, "El héroe no tiene que actuar ahora")
    return rec


@router.post("/{sid}/act")
def act(sid: str, req: schemas.ActRequest):
    s = get(sid)
    try:
        return s.hero_act(req.action, req.amount)
    except IllegalAction as exc:
        raise HTTPException(400, str(exc))


@router.post("/{sid}/deal")
def deal(sid: str):
    s = get(sid)
    if s.game.hand_in_progress:
        raise HTTPException(409, "Hay una mano en curso")
    if s.game.finished:
        raise HTTPException(409, "El torneo ha terminado")
    s.game.start_hand()
    s.run_until_hero()
    return s.state()


@router.post("/{sid}/undo")
def undo(sid: str):
    try:
        return get(sid).undo()
    except IllegalAction as exc:
        raise HTTPException(400, str(exc))


@router.post("/{sid}/compare")
def compare(sid: str, req: schemas.CompareRequest):
    try:
        return {"results": get(sid).compare(req.actions)}
    except IllegalAction as exc:
        raise HTTPException(400, str(exc))


@router.post("/{sid}/pause")
def pause(sid: str):
    s = get(sid)
    s.game.pause()
    return s.state()


@router.post("/{sid}/resume")
def resume(sid: str):
    s = get(sid)
    s.game.resume()
    return s.state()


@router.post("/{sid}/advance-time")
def advance_time(sid: str, req: schemas.AdvanceTimeRequest):
    s = get(sid)
    s.game.advance_time(req.seconds)
    return s.state()


@router.get("/{sid}/history")
def history(sid: str):
    s = get(sid)
    return {"hands": [r.to_dict() for r in s.game.results], "actions": [a.to_dict() for a in s.game.history],
            "decisions": [{"hand_no": d.hand_no, "street": d.street, "recommendation": d.recommendation, "taken": d.taken}
                          for d in s.decisions]}


@router.delete("/{sid}")
def delete(sid: str):
    SESSIONS.pop(sid, None)
    return {"ok": True}
