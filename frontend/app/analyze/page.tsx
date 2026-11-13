"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Recommendation } from "@/lib/types";
import { AnalysisPanel } from "@/components/AnalysisPanel";
import { pct } from "@/lib/cards";

interface Villain { name: string; position: string; stack: number; committed: number; folded: boolean; all_in: boolean; preflop_action: string; }
const ACTIONS = ["unknown", "open_raise", "limp", "call", "3bet", "shove", "call_shove", "check"];

export default function AnalyzePage() {
  const [form, setForm] = useState({ hero_cards: "Ah Kd", board: "", hero_position: "BB", hero_stack: 280, hero_committed: 20, pot: 550, to_call: 280, bb_size: 20, ante: 0, street: "preflop", raise_count_preflop: 1, players_remaining: 2, payouts: "" });
  const [villains, setVillains] = useState<Villain[]>([{ name: "Rival SB", position: "SB", stack: 0, committed: 530, folded: false, all_in: true, preflop_action: "shove" }]);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [eq, setEq] = useState<{ hero: string; villains: string; board: string; mode: string }>({ hero: "Ah Kh", villains: "QQ+, AKs", board: "", mode: "auto" });
  const [eqRes, setEqRes] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  async function run() {
    setLoading(true); setError(null);
    try {
      const payouts = form.payouts.trim() ? form.payouts.split(",").map((x) => parseFloat(x)) : null;
      setRec(await api.post<Recommendation>("/api/analysis/recommend", { ...form, payouts, villains }));
    } catch (e) { setError((e as Error).message); } finally { setLoading(false); }
  }

  async function runEquity() {
    setError(null);
    try {
      setEqRes(await api.post("/api/analysis/equity", { hero: eq.hero, villains: eq.villains.split(";").map((s) => s.trim()).filter(Boolean), board: eq.board, mode: eq.mode, samples: 30000 }));
    } catch (e) { setError((e as Error).message); }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
      <div className="space-y-4">
        <div className="card-panel p-5">
          <h1 className="text-xl font-semibold">Analizar una situación</h1>
          <p className="mt-1 text-xs text-slate-400">Introduce la situación tal y como la ves en la mesa. El bote incluye todas las fichas ya en el medio (ciegas, antes y apuestas). Las acciones preflop de los rivales determinan sus rangos estimados.</p>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Field label="Tus cartas"><input className="input" value={form.hero_cards} onChange={(e) => set("hero_cards", e.target.value)} /></Field>
            <Field label="Mesa (board)"><input className="input" placeholder="Qh 7h 2c" value={form.board} onChange={(e) => set("board", e.target.value)} /></Field>
            <Field label="Calle">
              <select className="input" value={form.street} onChange={(e) => set("street", e.target.value)}>
                {["preflop", "flop", "turn", "river"].map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
            <Field label="Tu posición">
              <select className="input" value={form.hero_position} onChange={(e) => set("hero_position", e.target.value)}>
                {["BTN", "SB", "BB", "BTN/SB"].map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
            <Num label="Tu stack (detrás)" v={form.hero_stack} on={(v) => set("hero_stack", v)} />
            <Num label="Ya puesto por ti" v={form.hero_committed} on={(v) => set("hero_committed", v)} />
            <Num label="Bote total" v={form.pot} on={(v) => set("pot", v)} />
            <Num label="A pagar" v={form.to_call} on={(v) => set("to_call", v)} />
            <Num label="Ciega grande" v={form.bb_size} on={(v) => set("bb_size", v)} />
            <Num label="Ante" v={form.ante} on={(v) => set("ante", v)} />
            <Num label="Subidas preflop previas" v={form.raise_count_preflop} on={(v) => set("raise_count_preflop", v)} />
            <Num label="Jugadores vivos" v={form.players_remaining} on={(v) => set("players_remaining", v)} />
            <Field label="Premios (opcional)"><input className="input" placeholder="0.8, 0.2" value={form.payouts} onChange={(e) => set("payouts", e.target.value)} /></Field>
          </div>
          <div className="mt-4 flex items-center justify-between">
            <div className="text-[11px] uppercase tracking-wider text-slate-400">Rivales</div>
            <button className="btn-ghost !py-1" onClick={() => setVillains([...villains, { name: `Rival ${villains.length + 1}`, position: "BTN", stack: 500, committed: 0, folded: false, all_in: false, preflop_action: "unknown" }])} disabled={villains.length >= 2}>+ rival</button>
          </div>
          {villains.map((v, i) => (
            <div key={i} className="mt-2 grid grid-cols-2 gap-2 rounded-lg border border-ink-600/50 p-2 sm:grid-cols-7">
              <input className="input" value={v.name} onChange={(e) => upd(i, { name: e.target.value })} />
              <select className="input" value={v.position} onChange={(e) => upd(i, { position: e.target.value })}>{["BTN", "SB", "BB", "BTN/SB"].map((s) => <option key={s}>{s}</option>)}</select>
              <input className="input" type="number" value={v.stack} onChange={(e) => upd(i, { stack: Number(e.target.value) })} title="stack detrás" />
              <input className="input" type="number" value={v.committed} onChange={(e) => upd(i, { committed: Number(e.target.value) })} title="ya puesto" />
              <select className="input" value={v.preflop_action} onChange={(e) => upd(i, { preflop_action: e.target.value })}>{ACTIONS.map((a) => <option key={a}>{a}</option>)}</select>
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={v.all_in} onChange={(e) => upd(i, { all_in: e.target.checked })} /> all-in</label>
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={v.folded} onChange={(e) => upd(i, { folded: e.target.checked })} /> fold <button className="ml-auto text-danger" onClick={() => setVillains(villains.filter((_, j) => j !== i))}>✕</button></label>
            </div>
          ))}
          <div className="mt-1 text-[11px] text-slate-500">Columnas: nombre (si coincide con un perfil guardado se usan sus estadísticas), posición, stack detrás, fichas ya puestas, acción preflop.</div>
          <button className="btn-primary mt-4" onClick={run} disabled={loading}>{loading ? "Calculando…" : "Recomendar"}</button>
          {error && <div className="mt-2 text-sm text-danger">{error}</div>}
        </div>

        <div className="card-panel p-5">
          <h2 className="text-lg font-semibold">Calculadora de equity</h2>
          <p className="mt-1 text-xs text-slate-400">Rangos en notación estándar (“22+, A2s+, KQo”), manos concretas (“QsQd”) o “top 35%”. Separa varios rivales con “;”. Enumeración exacta cuando es viable; si no, Monte Carlo con error estándar.</p>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Field label="Héroe"><input className="input" value={eq.hero} onChange={(e) => setEq({ ...eq, hero: e.target.value })} /></Field>
            <Field label="Rival(es)"><input className="input" value={eq.villains} onChange={(e) => setEq({ ...eq, villains: e.target.value })} /></Field>
            <Field label="Mesa"><input className="input" value={eq.board} onChange={(e) => setEq({ ...eq, board: e.target.value })} /></Field>
            <Field label="Método"><select className="input" value={eq.mode} onChange={(e) => setEq({ ...eq, mode: e.target.value })}><option value="auto">auto</option><option value="exact">exacto</option><option value="mc">Monte Carlo</option></select></Field>
          </div>
          <button className="btn-ghost mt-3" onClick={runEquity}>Calcular equity</button>
          {eqRes && (
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <Stat label="Equity" v={pct(eqRes.equity as number, 2)} />
              <Stat label="Gana" v={pct(eqRes.win as number, 2)} />
              <Stat label="Empata" v={pct(eqRes.tie as number, 2)} />
              <Stat label="Método" v={eqRes.method === "exact" ? "exacto" : `MC ${eqRes.samples} (±${pct(eqRes.ci95 as number, 2)})`} />
            </div>
          )}
        </div>
      </div>
      <aside><AnalysisPanel rec={rec} bb={form.bb_size} loading={loading} situation={{ ...form, villains }} /></aside>
    </div>
  );

  function upd(i: number, patch: Partial<Villain>) { setVillains(villains.map((v, j) => (j === i ? { ...v, ...patch } : v))); }
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <div><label className="label">{label}</label>{children}</div>; }
function Num({ label, v, on }: { label: string; v: number; on: (v: number) => void }) { return <Field label={label}><input className="input" type="number" value={v} onChange={(e) => on(Number(e.target.value))} /></Field>; }
function Stat({ label, v }: { label: string; v: string }) { return <div><div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div><div className="font-mono text-lg">{v}</div></div>; }
