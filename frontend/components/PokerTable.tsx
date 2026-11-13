"use client";
import { PlayingCard } from "./PlayingCard";
import type { GameState, PlayerState } from "@/lib/types";
import { bbs } from "@/lib/cards";

const SEAT_POS = [
  "left-1/2 bottom-0 -translate-x-1/2",
  "left-[1%] top-0",
  "right-[1%] top-0",
];

function Seat({ p, state, reveal }: { p: PlayerState; state: GameState; reveal: boolean }) {
  const active = state.hand_in_progress && state.to_act === p.seat;
  const isButton = state.button_seat === p.seat;
  const cards = p.hole_cards.length ? p.hole_cards : [];
  return (
    <div className={`flex flex-col items-center gap-1 ${p.folded && state.hand_in_progress ? "opacity-50" : ""}`}>
      <div className="flex gap-1">
        {cards.map((c, i) => (
          <PlayingCard key={i} code={p.is_hero || reveal ? c : "??"} size={p.is_hero ? "md" : "sm"} dim={p.folded} />
        ))}
      </div>
      <div className={`card-panel min-w-[118px] px-2 py-1 text-center sm:min-w-[132px] sm:px-3 sm:py-1.5 ${active ? "shadow-glow border-accent/60" : ""} ${p.eliminated ? "opacity-40" : ""}`}>
        <div className="flex items-center justify-center gap-2 text-xs">
          <span className={`font-semibold ${p.is_hero ? "text-accent" : "text-slate-200"}`}>{p.name}</span>
          {p.position && <span className="tag bg-ink-600 text-slate-300">{p.position}</span>}
          {isButton && <span className="tag bg-gold/20 text-gold">D</span>}
        </div>
        <div className="font-mono text-sm text-slate-100">
          {p.eliminated ? `${p.finish_place}º` : p.stack} {!p.eliminated && <span className="text-[10px] text-slate-400">{bbs(p.stack, state.level.big_blind)}</span>}
        </div>
        {p.all_in && !p.eliminated && <div className="text-[10px] uppercase tracking-wider text-gold">all-in</div>}
        {p.folded && state.hand_in_progress && !p.eliminated && <div className="text-[10px] uppercase tracking-wider text-slate-400">fold</div>}
      </div>
      {p.bet_this_street > 0 && state.hand_in_progress && (
        <div className="rounded-full bg-ink-900/80 px-2 py-0.5 font-mono text-xs text-gold">{p.bet_this_street}</div>
      )}
    </div>
  );
}

export function PokerTable({ state, reveal = false }: { state: GameState; reveal?: boolean }) {
  const ordered = [...state.players].sort((a, b) => ((a.seat - state.hero_seat + 3) % 3) - ((b.seat - state.hero_seat + 3) % 3));
  return (
    <div className="relative mx-auto aspect-square w-full max-w-3xl select-none sm:aspect-[16/10]">
      <div className="table-felt absolute left-[4%] right-[4%] top-[17%] bottom-[21%] rounded-[999px] border-[8px] border-ink-700 shadow-[inset_0_0_60px_rgba(0,0,0,0.6)] sm:left-[9%] sm:right-[9%] sm:top-[14%] sm:bottom-[20%] sm:border-[10px]">
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
          <div className="hidden text-[10px] uppercase tracking-[0.25em] text-emerald-200/50 sm:block">PokerMind AI · Twister</div>
          <div className="flex gap-1 sm:gap-1.5">
            {state.board.map((c, i) => <PlayingCard key={i} code={c} size="md" />)}
            {Array.from({ length: 5 - state.board.length }).map((_, i) => (
              <div key={`e${i}`} className="h-14 w-10 rounded-md border border-dashed border-emerald-200/15" />
            ))}
          </div>
          <div className="rounded-full bg-ink-950/60 px-3 py-1 font-mono text-sm text-gold">
            Bote {state.pot} <span className="text-[10px] text-slate-400">{bbs(state.pot, state.level.big_blind)}</span>
          </div>
          <div className="px-2 text-center text-[10px] text-emerald-100/60 sm:text-[11px]">
            Mano #{state.hand_no} · Nivel {state.level.level} · {state.level.small_blind}/{state.level.big_blind}
            {state.level.ante ? ` · ante ${state.level.ante}` : ""} · {state.street}
          </div>
        </div>
      </div>
      {ordered.map((p, i) => (
        <div key={p.seat} className={`absolute ${SEAT_POS[i]}`}>
          <Seat p={p} state={state} reveal={reveal} />
        </div>
      ))}
    </div>
  );
}
