export type Provenance = "exact" | "monte_carlo" | "nash" | "heuristic" | "n/a";

export interface Alternative {
  action: string;
  amount: number;
  ev_bb: number | null;
  ev_icm: number | null;
  ev_type: Provenance | string;
  note: string;
}

export interface EquityInfo {
  equity: number;
  win: number;
  tie: number;
  lose: number;
  method: string;
  samples: number;
  std_error: number;
  ci95: number;
  opponents: number;
  villain_equities: number[];
  notes: string[];
}

export interface PotOddsInfo {
  pot: number;
  to_call: number;
  ratio: number | null;
  ratio_text: string;
  required_equity: number;
}

export interface VillainRange {
  villain?: string;
  position?: string;
  percent: number;
  combos: number;
  text: string;
  grid: Record<string, number>;
  basis: string;
  confidence: string;
  assumptions: string[];
}

export interface Recommendation {
  action: string;
  amount: number;
  confidence: string;
  confidence_score: number;
  alternatives: Alternative[];
  explanation: string[];
  equity: EquityInfo | null;
  pot_odds: PotOddsInfo | null;
  villain_ranges: VillainRange[];
  gto_comparison: Record<string, unknown> | null;
  sources: string[];
  hero_hand_class: string;
  hero_hand_percentile: number | null;
  warnings: string[];
}

export interface PlayerState {
  seat: number;
  name: string;
  stack: number;
  is_hero: boolean;
  bot_profile: string;
  hole_cards: string[];
  folded: boolean;
  all_in: boolean;
  bet_this_street: number;
  committed: number;
  eliminated: boolean;
  finish_place: number | null;
  position: string;
}

export interface LegalActions {
  can_fold: boolean;
  can_check: boolean;
  can_call: boolean;
  call_amount: number;
  can_bet: boolean;
  can_raise: boolean;
  min_raise_to: number;
  max_raise_to: number;
  min_bet: number;
  max_bet: number;
}

export interface ActionRecord {
  hand_no: number;
  street: string;
  seat: number;
  name: string;
  action: string;
  amount: number;
  pot_after: number;
  stack_after: number;
}

export interface HandResult {
  hand_no: number;
  board: string[];
  winners: { seat: number; name: string; amount: number; hand: string | null }[];
  showdown: { seat: number; name: string; cards: string[]; hand: string }[];
  eliminated: number[];
}

export interface GameState {
  session_id: string;
  hero_seat: number;
  hero_to_act: boolean;
  hand_no: number;
  level: { level: number; small_blind: number; big_blind: number; ante: number; duration_seconds: number };
  level_index: number;
  elapsed_seconds: number;
  time_to_next_level: number | null;
  paused: boolean;
  button_seat: number;
  street: string;
  board: string[];
  pot: number;
  current_bet: number;
  to_act: number | null;
  hand_in_progress: boolean;
  finished: boolean;
  heads_up: boolean;
  players: PlayerState[];
  legal_actions: LegalActions | null;
  actions: ActionRecord[];
  last_result: HandResult | null;
  payouts: Record<string, number>;
  event_log: string[];
  decisions: number;
  bot_styles: Record<string, string>;
  config: { payouts: number[]; prize_pool: number; starting_stack: number; level_mode: string };
}

export interface StatInfo {
  value: number | null;
  n: number;
  ci95: [number, number];
  prior: number | null;
  shrunk: number | null;
}

export interface Profile {
  name: string;
  hands: number;
  confidence: string;
  style: string;
  vpip: StatInfo;
  pfr: StatInfo;
  three_bet: StatInfo;
  fold_to_three_bet: StatInfo;
  cbet: StatInfo;
  fold_to_cbet: StatInfo;
  wtsd: StatInfo;
  aggression_factor: number | null;
  aggressive_actions: number;
  passive_actions: number;
  bet_sizes: Record<string, number>;
  notes: string;
  warning: string | null;
}

export interface CompareResult {
  action: { action: string; amount?: number };
  error?: string;
  hero_stack_after?: number;
  chip_delta?: number;
  board?: string[];
  note?: string;
}
