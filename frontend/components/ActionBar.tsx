"use client";
import { useEffect, useState } from "react";
import type { LegalActions } from "@/lib/types";

export function ActionBar({ legal, bb, onAct, disabled, suggested }: {
  legal: LegalActions | null; bb: number; onAct: (action: string, amount: number) => void; disabled?: boolean;
  suggested?: { action: string; amount: number } | null;
}) {
  const isRaise = !!legal?.can_raise;
  const min = isRaise ? legal?.min_raise_to ?? 0 : legal?.min_bet ?? 0;
  const max = isRaise ? legal?.max_raise_to ?? 0 : legal?.max_bet ?? 0;
  const [amount, setAmount] = useState(min);
  useEffect(() => {
    setAmount(suggested && (suggested.action === "raise" || suggested.action === "bet") ? suggested.amount : min);
  }, [min, suggested]);
  if (!legal) return null;
  const canSize = legal.can_raise || legal.can_bet;
  const hl = (a: string) => (suggested?.action === a || (suggested?.action === "allin" && a === "allin") ? "ring-2 ring-accent/70" : "");
  return (
    <div className="card-panel flex flex-wrap items-center gap-2 p-3">
      {legal.can_fold && !legal.can_check && <button className={`btn-danger ${hl("fold")}`} disabled={disabled} onClick={() => onAct("fold", 0)}>Fold</button>}
      {legal.can_check && <button className={`btn-ghost ${hl("check")}`} disabled={disabled} onClick={() => onAct("check", 0)}>Check</button>}
      {legal.can_call && <button className={`btn-ghost ${hl("call")}`} disabled={disabled} onClick={() => onAct("call", 0)}>Call {legal.call_amount}</button>}
      {canSize && (
        <>
          <div className="flex items-center gap-2">
            <input type="range" min={min} max={max} step={Math.max(1, Math.floor(bb / 2))} value={Math.min(Math.max(amount, min), max)} onChange={(e) => setAmount(Number(e.target.value))} className="w-28 accent-teal-300 sm:w-40" />
            <input type="number" className="input w-24" min={min} max={max} value={amount} onChange={(e) => setAmount(Number(e.target.value))} />
            <span className="text-xs text-slate-400">{bb ? `${(amount / bb).toFixed(1)}bb` : ""}</span>
          </div>
          <button className={`btn-primary ${hl(isRaise ? "raise" : "bet")}`} disabled={disabled} onClick={() => onAct(isRaise ? "raise" : "bet", Math.min(Math.max(amount, min), max))}>
            {isRaise ? "Raise a" : "Bet"} {Math.min(Math.max(amount, min), max)}
          </button>
          <button className={`btn-ghost border-gold/50 text-gold ${hl("allin")}`} disabled={disabled} onClick={() => onAct(isRaise ? "raise" : "bet", max)}>All-in {max}</button>
        </>
      )}
    </div>
  );
}
