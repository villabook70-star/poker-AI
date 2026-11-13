"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Recommendation } from "@/lib/types";
import { actionLabel } from "@/lib/cards";
import { AnalysisPanel } from "@/components/AnalysisPanel";

interface Decision { street: string; board: string[]; pot: number; to_call: number; taken: { action: string; amount: number }; recommendation: Recommendation & { error?: string }; agrees: boolean | null; ev_loss_bb: number | null; }
interface HandAnalysis { hand_id: string; hero: string; hero_cards: string[]; board: string[]; blinds: string; decisions: Decision[]; total_ev_loss_bb: number; mistakes: number; skipped?: string; }
interface ImportResult { session_id: number; summary: { hands: number; decisions: number; mistakes: number; ev_loss_bb_estimate: number; warnings: string[]; note: string }; hands: HandAnalysis[]; }
interface SessionRow { id: number; name: string; source: string; created_at: number; hands: number; summary: ImportResult["summary"]; }

export default function ImportPage() {
  const [text, setText] = useState("");
  const [name, setName] = useState("Sesión " + new Date().toLocaleDateString());
  const [hero, setHero] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [sel, setSel] = useState<Decision | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.get<SessionRow[]>("/api/import/sessions").then(setSessions).catch(() => {});
  useEffect(() => { load(); }, []);

  async function run() {
    setBusy(true); setError(null);
    try { setResult(await api.post<ImportResult>("/api/import", { text, name, hero: hero || null, format: "auto" })); load(); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function open(id: number) {
    const s = await api.get<{ id: number; summary: ImportResult["summary"]; hands: { analysis: HandAnalysis }[] }>(`/api/import/sessions/${id}`);
    setResult({ session_id: s.id, summary: s.summary, hands: s.hands.map((h) => h.analysis) });
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
      <div className="space-y-4">
        <div className="card-panel p-5">
          <h1 className="text-xl font-semibold">Importar partidas terminadas</h1>
          <p className="mt-1 text-xs text-slate-400">Pega historiales de manos en formato PokerStars o el JSON genérico de PokerMind (docs/IMPORT_FORMAT.md). Se reconstruye cada mano y se analiza cada decisión tuya con el motor. Las grabaciones de vídeo no se procesan directamente: conviértelas al JSON genérico con una herramienta externa.</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <div><label className="label">Nombre de la sesión</label><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div><label className="label">Tu nombre en la mesa (opcional)</label><input className="input" value={hero} onChange={(e) => setHero(e.target.value)} placeholder="se detecta de 'Dealt to'" /></div>
          </div>
          <textarea className="input mt-2 font-mono text-xs" rows={10} value={text} onChange={(e) => setText(e.target.value)} placeholder="PokerStars Hand #...&#10;Seat 1: Hero (500 in chips)..." />
          <div className="mt-2 flex items-center gap-3">
            <button className="btn-primary" onClick={run} disabled={busy || !text.trim()}>{busy ? "Analizando…" : "Importar y analizar"}</button>
            {error && <span className="text-sm text-danger">{error}</span>}
          </div>
        </div>
        {result && (
          <div className="card-panel p-5">
            <div className="flex flex-wrap gap-2 text-sm">
              <span className="tag bg-ink-600 text-slate-300">{result.summary.hands} manos</span>
              <span className="tag bg-ink-600 text-slate-300">{result.summary.decisions} decisiones</span>
              <span className="tag bg-danger/15 text-danger">{result.summary.mistakes} errores (ΔEV ≥ 0.3bb)</span>
              <span className="tag bg-warn/15 text-warn">pérdida EV estimada {result.summary.ev_loss_bb_estimate} bb</span>
            </div>
            <div className="mt-1 text-[11px] text-slate-500">{result.summary.note} {result.summary.warnings.join(" ")}</div>
            <div className="mt-3 space-y-2">
              {result.hands.map((h) => (
                <div key={h.hand_id} className="rounded-lg border border-ink-600/50 p-3">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <b>#{h.hand_id}</b> <span className="text-accent">{h.hero_cards?.join(" ")}</span>
                    <span className="text-slate-400">{h.blinds} · board {h.board?.join(" ") || "—"}</span>
                    {h.mistakes > 0 && <span className="tag bg-danger/15 text-danger">{h.mistakes} error(es)</span>}
                    {h.skipped && <span className="tag bg-ink-600 text-slate-400">{h.skipped}</span>}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {h.decisions.map((d, i) => (
                      <button key={i} onClick={() => setSel(d)} className={`rounded-md border px-2 py-1 text-xs ${d.agrees === false ? "border-danger/50 text-danger" : "border-ok/40 text-ok"} hover:bg-ink-700`}>
                        {d.street}: {actionLabel(d.taken.action)}{d.taken.amount ? ` ${d.taken.amount}` : ""} → {d.recommendation.action ? actionLabel(d.recommendation.action) : "?"}
                        {d.ev_loss_bb ? ` (−${d.ev_loss_bb}bb)` : ""}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="card-panel p-5">
          <h2 className="text-lg font-semibold">Sesiones guardadas</h2>
          {sessions.length === 0 && <div className="mt-1 text-sm text-slate-400">Ninguna todavía.</div>}
          <ul className="mt-2 divide-y divide-ink-600/50 text-sm">
            {sessions.map((s) => (
              <li key={s.id} className="flex items-center gap-3 py-2">
                <button className="text-accent hover:underline" onClick={() => open(s.id)}>{s.name}</button>
                <span className="text-xs text-slate-500">{new Date(s.created_at * 1000).toLocaleString()} · {s.hands} manos · {s.summary.mistakes} errores</span>
                <button className="btn-danger ml-auto !px-2 !py-0.5 text-xs" onClick={() => api.del(`/api/import/sessions/${s.id}`).then(load)}>✕</button>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <aside className="space-y-3">
        {sel ? (
          <>
            <div className="card-panel p-3 text-sm">
              <div className="text-[11px] uppercase tracking-wider text-slate-500">Decisión seleccionada</div>
              <div>{sel.street} · bote {sel.pot} · a pagar {sel.to_call} · board {sel.board.join(" ") || "—"}</div>
              <div>Jugaste: <b>{actionLabel(sel.taken.action)} {sel.taken.amount || ""}</b> · {sel.agrees ? <span className="text-ok">coincide con la recomendación</span> : <span className="text-danger">difiere de la recomendación</span>}</div>
            </div>
            {sel.recommendation.error ? <div className="card-panel p-3 text-sm text-danger">{sel.recommendation.error}</div> : <AnalysisPanel rec={sel.recommendation} />}
          </>
        ) : <div className="card-panel p-4 text-sm text-slate-400">Selecciona una decisión para ver el análisis completo.</div>}
      </aside>
    </div>
  );
}
