"use client";
import { useState } from "react";
import type { Recommendation } from "@/lib/types";
import { actionLabel, pct } from "@/lib/cards";
import { ConfidenceBadge, ProvenanceBadge } from "./ProvenanceBadge";
import { RangeGrid } from "./RangeGrid";
import { api } from "@/lib/api";

export function AnalysisPanel({ rec, bb, loading, situation }: { rec: Recommendation | null; bb?: number; loading?: boolean; situation?: unknown }) {
  const [explain, setExplain] = useState<{ text: string; provider: string; note?: string } | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [showRanges, setShowRanges] = useState(false);

  async function askExplanation() {
    if (!rec) return;
    setExplaining(true);
    try {
      setExplain(await api.post("/api/analysis/explain", { recommendation: rec, situation }));
    } catch (e) {
      setExplain({ text: `Error: ${(e as Error).message}`, provider: "error" });
    } finally {
      setExplaining(false);
    }
  }

  if (loading) return <div className="card-panel p-4 text-sm text-slate-400">Calculando…</div>;
  if (!rec) return <div className="card-panel p-4 text-sm text-slate-400">Sin recomendación: espera tu turno o describe una situación.</div>;

  const amountTxt = rec.amount ? ` ${rec.amount}${bb ? ` (${(rec.amount / bb).toFixed(1)}bb)` : ""}` : "";
  return (
    <div className="flex flex-col gap-3">
      <div className="card-panel p-4">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="text-[11px] uppercase tracking-wider text-slate-400">Recomendación</span>
          <ConfidenceBadge level={rec.confidence} score={rec.confidence_score} />
          {rec.sources.map((s) => <ProvenanceBadge key={s} type={s} />)}
        </div>
        <div className="text-2xl font-semibold text-accent">
          {actionLabel(rec.action)}
          <span className="text-slate-200">{amountTxt}</span>
        </div>
        <div className="mt-1 text-xs text-slate-400">
          Mano {rec.hero_hand_class}
          {rec.hero_hand_percentile !== null ? ` · top ${rec.hero_hand_percentile}% preflop` : ""}
        </div>
        {rec.gto_comparison && (
          <div className="mt-2 rounded-lg border border-violet-400/30 bg-violet-400/5 p-2 text-xs text-violet-200">
            {rec.gto_comparison.available ? (
              <>
                <b>Comparación Nash:</b> {String(rec.gto_comparison.source)} → {String(rec.gto_comparison.nash_action ?? "")}
                {rec.gto_comparison.push_frequency !== undefined && ` (push ${pct(rec.gto_comparison.push_frequency as number, 0)})`}
                {rec.gto_comparison.call_frequency !== undefined && ` (call ${pct(rec.gto_comparison.call_frequency as number, 0)})`}
              </>
            ) : (
              <>
                <b>Sin datos GTO verificados:</b> {String(rec.gto_comparison.reason)}
              </>
            )}
          </div>
        )}
      </div>

      {(rec.equity || rec.pot_odds) && (
        <div className="card-panel grid grid-cols-2 gap-3 p-4 text-sm sm:grid-cols-4">
          {rec.equity && (
            <>
              <Stat label="Equity" value={pct(rec.equity.equity)} sub={rec.equity.method === "exact" ? "exacta" : `MC ±${pct(rec.equity.ci95)} (${rec.equity.samples})`} />
              <Stat label="Gana / Empata" value={`${pct(rec.equity.win, 0)} / ${pct(rec.equity.tie, 0)}`} />
            </>
          )}
          {rec.pot_odds && (
            <>
              <Stat label="Pot odds" value={rec.pot_odds.ratio_text} sub={`bote ${rec.pot_odds.pot} · pagar ${rec.pot_odds.to_call}`} />
              <Stat label="Equity mínima" value={pct(rec.pot_odds.required_equity)} sub={rec.equity ? (rec.equity.equity > rec.pot_odds.required_equity ? "✓ superada" : "✗ no alcanzada") : undefined} />
            </>
          )}
        </div>
      )}

      <div className="card-panel p-4">
        <div className="mb-2 text-[11px] uppercase tracking-wider text-slate-400">Alternativas y valor esperado</div>
        <table className="w-full text-sm">
          <tbody>
            {rec.alternatives.map((a, i) => (
              <tr key={i} className={`border-t border-ink-600/50 ${a.action === rec.action ? "text-accent" : "text-slate-200"}`}>
                <td className="py-1.5 font-medium">
                  {actionLabel(a.action)} {a.amount ? <span className="font-mono text-xs text-slate-400">{a.amount}</span> : null}
                </td>
                <td className="py-1.5 text-right font-mono">{a.ev_bb === null ? "—" : `${a.ev_bb >= 0 ? "+" : ""}${a.ev_bb.toFixed(2)} bb`}</td>
                <td className="py-1.5 pl-2 text-right">
                  <ProvenanceBadge type={a.ev_type} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rec.alternatives.some((a) => a.note) && (
          <ul className="mt-2 space-y-0.5 text-[11px] text-slate-400">
            {rec.alternatives.filter((a) => a.note).map((a, i) => (
              <li key={i}>
                <b className="text-slate-300">{actionLabel(a.action)}:</b> {a.note}
                {a.ev_icm !== null && a.ev_icm !== undefined ? ` · ΔICM ${a.ev_icm >= 0 ? "+" : ""}${(a.ev_icm * 100).toFixed(2)}% del premio` : ""}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card-panel p-4">
        <div className="mb-2 text-[11px] uppercase tracking-wider text-slate-400">Explicación matemática</div>
        <ol className="list-decimal space-y-1 pl-4 text-sm text-slate-200">
          {rec.explanation.map((l, i) => <li key={i}>{l}</li>)}
        </ol>
        {rec.warnings.length > 0 && (
          <ul className="mt-3 space-y-1 border-t border-ink-600/50 pt-2 text-xs text-warn/90">
            {rec.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
          </ul>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          <button className="btn-ghost" onClick={askExplanation} disabled={explaining}>
            {explaining ? "Explicando…" : "Explicar con IA"}
          </button>
          {rec.villain_ranges.length > 0 && (
            <button className="btn-ghost" onClick={() => setShowRanges((v) => !v)}>
              {showRanges ? "Ocultar rangos" : `Rangos estimados (${rec.villain_ranges.length})`}
            </button>
          )}
        </div>
        {explain && (
          <div className="mt-3 whitespace-pre-wrap rounded-lg border border-ink-600/60 bg-ink-900/60 p-3 text-sm text-slate-200">
            <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">
              {explain.provider === "claude" ? "Claude (sin cálculos propios: usa los números del motor)" : "Explicación determinista (sin API de Claude)"}
              {explain.note ? ` · ${explain.note}` : ""}
            </div>
            {explain.text}
          </div>
        )}
      </div>

      {showRanges && rec.villain_ranges.map((vr, i) => (
        <div key={i} className="card-panel p-4">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
            <b>{vr.villain ?? "Rival"}</b>
            <span className="text-slate-400">{vr.position}</span>
            <span className="tag bg-ink-600 text-slate-300">{vr.percent}% · {vr.combos} combos</span>
            <span className="tag bg-warn/15 text-warn">confianza {vr.confidence}</span>
          </div>
          <div className="mb-2 text-xs text-slate-400">{vr.basis}</div>
          <RangeGrid grid={vr.grid} />
          <ul className="mt-2 space-y-0.5 text-[11px] text-slate-500">
            {vr.assumptions.map((a, j) => <li key={j}>• {a}</li>)}
          </ul>
        </div>
      ))}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="font-mono text-lg text-slate-100">{value}</div>
      {sub && <div className="text-[11px] text-slate-400">{sub}</div>}
    </div>
  );
}
