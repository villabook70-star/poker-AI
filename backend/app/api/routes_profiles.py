from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..analysis.profiles import OpponentProfile, Stat
from ..storage.db import Database
from . import schemas

router = APIRouter(prefix="/api/profiles", tags=["profiles"])
_db: Database | None = None


def db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


@router.get("")
def list_profiles():
    return [p.to_dict() for p in db().list_profiles()]


@router.get("/{name}")
def get_profile(name: str):
    p = db().get_profile(name)
    if not p:
        raise HTTPException(404, "Perfil no encontrado")
    return p.to_dict()


@router.post("")
def upsert_profile(req: schemas.ProfileIn):
    p = db().get_profile(req.name) or OpponentProfile(name=req.name)
    p.hands = req.hands or p.hands
    for key in ("vpip", "pfr", "three_bet", "fold_to_three_bet", "cbet", "fold_to_cbet", "wtsd"):
        st = getattr(req, key)
        if st is not None and st.n:
            setattr(p, key, Stat(successes=(st.value or 0.0) * st.n, opportunities=st.n))
    if req.aggressive_actions:
        p.aggressive_actions = req.aggressive_actions
    if req.passive_actions:
        p.passive_actions = req.passive_actions
    if req.bet_sizes:
        p.bet_sizes.update(req.bet_sizes)
    if req.notes:
        p.notes = req.notes
    db().save_profile(p)
    return p.to_dict()


@router.delete("/{name}")
def delete_profile(name: str):
    if not db().delete_profile(name):
        raise HTTPException(404, "Perfil no encontrado")
    return {"ok": True}
