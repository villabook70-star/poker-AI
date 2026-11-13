"""Pydantic request/response schemas for the API."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class EvaluateRequest(BaseModel):
    cards: str = Field(..., description="5-7 cartas, p.ej. 'As Kd Qs Js Ts 2c 3d' o 'AsKdQsJsTs'")


class EquityRequest(BaseModel):
    hero: str = Field(..., description="Dos cartas, p.ej. 'AhKh'")
    villains: List[str] = Field(..., description="Rangos en notación estándar o manos concretas ('QsQd'), uno por rival")
    board: str = ""
    dead: str = ""
    mode: str = Field("auto", pattern="^(auto|exact|mc)$")
    samples: int = Field(20000, ge=1000, le=500000)
    seed: Optional[int] = None


class PotOddsRequest(BaseModel):
    pot: float = Field(..., ge=0, description="Bote total incluyendo la apuesta del rival")
    to_call: float = Field(..., ge=0)
    equity: Optional[float] = Field(None, ge=0, le=1)


class RangeParseRequest(BaseModel):
    text: str


class RangeTopRequest(BaseModel):
    percent: float = Field(..., ge=0, le=100)


class RangeEstimateRequest(BaseModel):
    action: str = "open_raise"
    position: str = "BTN"
    profile_name: Optional[str] = None
    stack_bb: float = 25.0


class BtnShoveRequest(BaseModel):
    hand: str = Field(..., description="Clase de mano, p.ej. 'A5s', 'KQo', '77'")
    stacks: List[float] = Field(..., min_length=3, max_length=3, description="[BTN, SB, BB] en fichas antes de poner ciegas")
    bb_size: float
    ante: float = 0
    payouts: Optional[List[float]] = None
    sb_call_range: Optional[str] = None
    bb_call_range: Optional[str] = None


class IcmRequest(BaseModel):
    stacks: List[float]
    payouts: List[float]


class PreflopRequest(BaseModel):
    position: str = "BTN"
    effective_bb: float = 25.0


class VillainIn(BaseModel):
    name: str
    position: str
    stack: int
    committed: int = 0
    folded: bool = False
    all_in: bool = False
    preflop_action: str = "unknown"
    profile_name: Optional[str] = None


class SituationIn(BaseModel):
    hero_cards: str
    board: str = ""
    hero_position: str
    hero_stack: int
    hero_committed: int = 0
    pot: int
    to_call: int = 0
    bb_size: int
    ante: int = 0
    street: str = "preflop"
    villains: List[VillainIn]
    payouts: Optional[List[float]] = None
    players_remaining: int = 3
    hero_preflop_action: str = "none"
    raise_count_preflop: int = 0
    legal: Optional[Dict] = None


class ExplainRequest(BaseModel):
    recommendation: Dict
    situation: Optional[Dict] = None
    use_claude: Optional[bool] = None


class NewSimRequest(BaseModel):
    config: Optional[Dict] = None
    bot_profiles: Optional[List[str]] = None
    seed: Optional[int] = None
    hero_name: str = "Héroe"


class ActRequest(BaseModel):
    action: str
    amount: int = 0


class CompareRequest(BaseModel):
    actions: List[Dict]


class AdvanceTimeRequest(BaseModel):
    seconds: float = Field(..., ge=0, le=36000)


class StatIn(BaseModel):
    value: Optional[float] = Field(None, ge=0, le=1)
    n: int = Field(0, ge=0)


class ProfileIn(BaseModel):
    name: str
    hands: int = 0
    vpip: Optional[StatIn] = None
    pfr: Optional[StatIn] = None
    three_bet: Optional[StatIn] = None
    fold_to_three_bet: Optional[StatIn] = None
    cbet: Optional[StatIn] = None
    fold_to_cbet: Optional[StatIn] = None
    wtsd: Optional[StatIn] = None
    aggressive_actions: int = 0
    passive_actions: int = 0
    bet_sizes: Optional[Dict[str, int]] = None
    notes: str = ""


class ImportRequest(BaseModel):
    format: str = Field("auto", pattern="^(auto|pokerstars|json)$")
    text: str
    name: str = "Sesión importada"
    hero: Optional[str] = None
    update_profiles: bool = True
