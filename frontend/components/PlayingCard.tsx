import { SUIT_SYMBOL } from "@/lib/cards";

const SUIT_ON_CARD: Record<string, string> = { s: "text-ink-950", h: "text-red-600", d: "text-sky-600", c: "text-emerald-700" };

export function PlayingCard({ code, size = "md", dim = false }: { code: string; size?: "sm" | "md" | "lg"; dim?: boolean }) {
  const sizes = { sm: "h-9 w-7 text-[11px]", md: "h-14 w-10 text-base", lg: "h-20 w-14 text-xl" };
  if (!code || code === "??") {
    return (
      <div className={`${sizes[size]} flex items-center justify-center rounded-md border border-ink-500 bg-gradient-to-br from-ink-600 to-ink-800 shadow-md`}>
        <div className="h-3/4 w-3/4 rounded-sm border border-ink-400/40 bg-[repeating-linear-gradient(45deg,#2a3650_0_3px,#1f2a3f_3px_6px)]" />
      </div>
    );
  }
  const rank = code[0] === "T" ? "10" : code[0];
  const suit = code[1];
  return (
    <div className={`${sizes[size]} flex flex-col items-center justify-center rounded-md border border-slate-300/30 bg-slate-50 font-bold leading-none shadow-md ${SUIT_ON_CARD[suit]} ${dim ? "opacity-40" : ""}`}>
      <span>{rank}</span>
      <span className="mt-0.5">{SUIT_SYMBOL[suit]}</span>
    </div>
  );
}
