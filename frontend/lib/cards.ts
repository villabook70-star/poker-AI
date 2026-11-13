export const SUIT_SYMBOL: Record<string, string> = { s: "♠", h: "♥", d: "♦", c: "♣" };
export const SUIT_COLOR: Record<string, string> = { s: "text-slate-100", h: "text-red-400", d: "text-sky-400", c: "text-emerald-400" };
export const RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"];

export function pct(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  return `${(x * 100).toFixed(digits)}%`;
}

export function bbs(chips: number, bb: number): string {
  return bb ? `${(chips / bb).toFixed(1)}bb` : "";
}

export function actionLabel(a: string): string {
  const m: Record<string, string> = { fold: "Fold", check: "Check", call: "Call", bet: "Bet", raise: "Raise", allin: "All-in" };
  return m[a] ?? a;
}

export function provenanceLabel(p: string): string {
  const m: Record<string, string> = {
    exact: "Exacto",
    monte_carlo: "Monte Carlo",
    nash: "Nash push/fold",
    heuristic: "Heurístico",
    "n/a": "Sin EV",
  };
  return m[p] ?? p;
}

export function provenanceClass(p: string): string {
  const m: Record<string, string> = {
    exact: "bg-ok/15 text-ok",
    monte_carlo: "bg-sky-400/15 text-sky-300",
    nash: "bg-violet-400/15 text-violet-300",
    heuristic: "bg-warn/15 text-warn",
    "n/a": "bg-slate-500/20 text-slate-400",
  };
  return m[p] ?? "bg-slate-500/20 text-slate-400";
}

export function gridLabel(row: number, col: number): string {
  const hi = RANKS[Math.min(row, col)];
  const lo = RANKS[Math.max(row, col)];
  if (row === col) return hi + hi;
  return row < col ? `${hi}${lo}s` : `${hi}${lo}o`;
}
