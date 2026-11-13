from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..ai.explain import claude_available, explain
from ..analysis.profiles import OpponentProfile
from ..analysis.range_model import estimate_preflop_range
from ..analysis.recommender import Situation, VillainInfo, recommend
from ..engine.cards import hand_class, parse_cards
from ..engine.equity import calculate_equity
from ..engine.evaluator import CATEGORY_NAMES, category, describe, evaluate
from ..engine.icm import icm_equities
from ..engine.pot_odds import ev_call, pot_odds
from ..engine.preflop import preflop_advice
from ..engine.pushfold import btn_shove_analysis, solve_hu_push_fold
from ..engine.ranges import Range, load_equity_data
from ..storage.db import Database
from . import schemas

router = APIRouter(prefix="/api/analysis", tags=["analysis"])
_db: Database | None = None


def db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def parse_range_or_hand(text: str) -> Range:
    t = text.strip()
    try:
        cards = parse_cards(t)
        if len(cards) == 2:
            return Range.single(cards[0], cards[1])
    except ValueError:
        pass
    if t.lower().startswith("top"):
        return Range.top_percent(float(t[3:].strip().rstrip("%")))
    return Range.from_text(t)


@router.post("/evaluate")
def evaluate_hand(req: schemas.EvaluateRequest):
    try:
        cards = parse_cards(req.cards)
        v = evaluate(cards)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"value": v, "category": CATEGORY_NAMES[category(v)], "description": describe(v), "description_en": describe(v, "en"),
            "method": "exact"}


@router.post("/equity")
def equity(req: schemas.EquityRequest):
    try:
        hero = parse_cards(req.hero)
        board = parse_cards(req.board) if req.board.strip() else []
        dead = parse_cards(req.dead) if req.dead.strip() else []
        villains = [parse_range_or_hand(v) for v in req.villains]
        res = calculate_equity(hero, villains, board, dead, req.mode, req.samples, req.seed)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    out = res.to_dict()
    out["hero_class"] = hand_class(*hero)
    out["villain_ranges"] = [{"text": v.to_text()[:200], "combos": v.combo_count(), "percent": round(v.percent_of_all(), 1)} for v in villains]
    return out


@router.post("/pot-odds")
def pot_odds_ep(req: schemas.PotOddsRequest):
    po = pot_odds(req.pot, req.to_call)
    out = po.to_dict()
    out["method"] = "exact"
    if req.equity is not None:
        out["ev_call"] = round(ev_call(req.equity, req.pot, req.to_call), 3)
        out["call_is_profitable"] = req.equity > po.required_equity
    return out


@router.post("/range/parse")
def range_parse(req: schemas.RangeParseRequest):
    try:
        r = parse_range_or_hand(req.text)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"text": r.to_text(), "combos": r.combo_count(), "percent": round(r.percent_of_all(), 2), "grid": r.class_weights()}


@router.post("/range/top")
def range_top(req: schemas.RangeTopRequest):
    r = Range.top_percent(req.percent)
    return {"text": r.to_text(), "combos": r.combo_count(), "percent": round(r.percent_of_all(), 2), "grid": r.class_weights(),
            "ranking_source": "equity vs mano aleatoria (Monte Carlo)" if load_equity_data() else "orden heurístico de respaldo (falta la matriz)"}


@router.post("/range/estimate")
def range_estimate(req: schemas.RangeEstimateRequest):
    prof = db().get_profile(req.profile_name) if req.profile_name else None
    est = estimate_preflop_range(req.action, req.position, prof, req.stack_bb)
    return est.to_dict()


@router.get("/pushfold/hu")
def pushfold_hu(stack_bb: float, ante_bb: float = 0.0):
    if not load_equity_data():
        raise HTTPException(503, "Matriz de equity no disponible; ejecuta scripts/build_equity_matrix.py")
    if not 1 <= stack_bb <= 60:
        raise HTTPException(400, "stack_bb debe estar entre 1 y 60")
    return solve_hu_push_fold(round(stack_bb, 1), round(ante_bb, 3)).to_dict()


@router.post("/pushfold/btn")
def pushfold_btn(req: schemas.BtnShoveRequest):
    if not load_equity_data():
        raise HTTPException(503, "Matriz de equity no disponible")
    try:
        sb_r = Range.from_text(req.sb_call_range) if req.sb_call_range else None
        bb_r = Range.from_text(req.bb_call_range) if req.bb_call_range else None
        return btn_shove_analysis(req.hand, req.stacks, req.bb_size, req.ante, req.payouts, sb_r, bb_r)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc))


@router.post("/icm")
def icm(req: schemas.IcmRequest):
    if not req.stacks or abs(sum(req.payouts) - 1) > 1e-6 and sum(req.payouts) > 1.5:
        pass
    eq = icm_equities(req.stacks, req.payouts)
    return {"equities": [round(e, 5) for e in eq], "model": "Malmuth-Harville", "method": "exact given the model"}


@router.post("/preflop")
def preflop(req: schemas.PreflopRequest):
    return preflop_advice(req.position, req.effective_bb).to_dict()


def situation_from_schema(s: schemas.SituationIn) -> Situation:
    profiles = db().all_profiles()
    villains = [VillainInfo(v.name, v.position, v.stack, v.committed, v.folded, v.all_in, v.preflop_action,
                            profiles.get(v.profile_name or v.name)) for v in s.villains]
    hero = parse_cards(s.hero_cards)
    board = parse_cards(s.board) if s.board.strip() else []
    legal = s.legal
    if legal is None:
        to_call = s.to_call
        legal = {"can_fold": True, "can_check": to_call == 0, "can_call": to_call > 0, "call_amount": min(to_call, s.hero_stack),
                 "can_bet": to_call == 0 and s.hero_stack > 0, "can_raise": to_call > 0 and s.hero_stack > to_call,
                 "min_raise_to": max(s.bb_size, 2 * (to_call + s.hero_committed)), "max_raise_to": s.hero_stack + s.hero_committed,
                 "min_bet": s.bb_size, "max_bet": s.hero_stack}
    return Situation(hero, board, s.hero_position, s.hero_stack, s.hero_committed, s.pot, s.to_call, s.bb_size, s.ante,
                     s.street, villains, legal, s.payouts, s.players_remaining, s.hero_preflop_action, s.raise_count_preflop)


@router.post("/recommend")
def recommend_ep(s: schemas.SituationIn):
    try:
        sit = situation_from_schema(s)
        rec = recommend(sit)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return rec.to_dict()


@router.post("/explain")
def explain_ep(req: schemas.ExplainRequest):
    payload = {"recommendation": req.recommendation, "situation": req.situation}
    return explain(payload, req.use_claude)


@router.get("/status")
def status():
    data = load_equity_data()
    return {"equity_matrix": bool(data), "equity_matrix_meta": (data or {}).get("meta"), "claude_available": claude_available()}
