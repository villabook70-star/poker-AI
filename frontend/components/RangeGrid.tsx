"use client";
import { gridLabel } from "@/lib/cards";

export function RangeGrid({ grid, title, small = false }: { grid: Record<string, number>; title?: string; small?: boolean }) {
  const cell = small ? "h-4 w-4 text-[6px]" : "h-6 w-6 text-[8px] sm:h-7 sm:w-7 sm:text-[9px]";
  return (
    <div>
      {title && <div className="mb-1 text-xs text-slate-400">{title}</div>}
      <div className="inline-grid grid-cols-13 gap-[1px] rounded-md bg-ink-700 p-[1px]" style={{ gridTemplateColumns: "repeat(13, minmax(0, 1fr))" }}>
        {Array.from({ length: 169 }, (_, i) => {
          const row = Math.floor(i / 13);
          const col = i % 13;
          const label = gridLabel(row, col);
          const w = grid[label] ?? 0;
          const bg = w > 0 ? `rgba(94, 234, 212, ${0.2 + 0.75 * w})` : row === col ? "#1a2334" : "#111826";
          const color = w > 0.5 ? "#07090d" : "#94a3b8";
          return (
            <div key={label} title={`${label}${w ? ` · ${(w * 100).toFixed(0)}%` : ""}`} className={`${cell} flex items-center justify-center rounded-[2px] font-mono`} style={{ background: bg, color }}>
              {label}
            </div>
          );
        })}
      </div>
    </div>
  );
}
