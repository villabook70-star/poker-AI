"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { CompareResult, GameState, Recommendation } from "@/lib/types";
import { PokerTable } from "@/components/PokerTable";
import { AnalysisPanel } from "@/components/AnalysisPanel";
import { ActionBar } from "@/components/ActionBar";
import { actionLabel } from "@/lib/cards";

const STYLES = ["balanced", "tight", "loose", "aggressive", "maniac"];

export default function SimulatorPage() {
  const [state, setState] = useState<GameState | null>(null);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [loadingRec, setLoadingRec] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRec, setShowRec] = useState(true);
  const [compare, setCompare] = useState<CompareResult[] | null>(null);
  const [bots, setBots] = useState<string[]>(["balanced", "aggressive"]);
  const [payouts, setPayouts] = useState("1.0");
  const [levelMode, setLevelMode] = useState<"time" | "hands">("time");
  const [styleLabels, setStyleLabels] = useState<Record<string, string>>({});
  const sid = useRef<string | null>(null);

  useEffect(() => {
    api.get<Record<string, string>>("/api/sim/bot-styles").then(setStyleLabels).catch(() => {});
  }, []);

  const fetchRec = useCallback(async (s: GameState) => {
    if (!s.hero_to_act) { setRec(null); return; }
    setLoadingRec(true);
    try {
      setRec(await api.get<Recommendation>(`/api/sim/${s.session_id}/recommend`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingRec(false);
    }
  }, []);

  const apply = useCallback(async (s: GameState) => {
    setState(s);
    setCompare(null);
    sid.current = s.session_id;
    await fetchRec(s);
  }, [fetchRec]);

  async function newGame() {
    setBusy(true); setError(null);
    try {
      const pays = payouts.split(",").map((x) => parseFloat(x.trim())).filter((x) => !Number.isNaN(x));
      const s = await api.post<GameState>("/api/sim/new", { bot_profiles: bots, config: { payouts: pays, level_mode: levelMode } });
      await apply(s);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function act(action: string, amount: number) {
    if (!sid.current) return;
    setBusy(true); setError(null);
    try { await apply(await api.post<GameState>(`/api/sim/${sid.current}/act`, { action, amount })); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function call(path: string, body?: unknown) {
    if (!sid.current) return;
    setBusy(true); setError(null);
    try { await apply(await api.post<GameState>(`/api/sim/${sid.current}/${path}`, body)); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function doCompare() {
    if (!sid.current || !state?.legal_actions) return;
    const la = state.legal_actions;
    const actions: { action: string; amount?: number }[] = [];
    if (la.can_fold && !la.can_check) actions.push({ action: "fold" });
    if (la.can_check) actions.push({ action: "check" });
    if (la.can_call) actions.push({ action: "call" });
    if (la.can_raise) { actions.push({ action: "raise", amount: la.min_raise_to }); if (la.max_raise_to !== la.min_raise_to) actions.push({ action: "raise", amount: la.max_raise_to }); }
    if (la.can_bet) { actions.push({ action: "bet", amount: Math.max(la.min_bet, Math.round(state.pot / 2)) }); actions.push({ action: "bet", amount: la.max_bet }); }
    setBusy(true);
    try { setCompare((await api.post<{ results: CompareResult[] }>(`/api/sim/${sid.current}/compare`, { actions })).results); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  if (!state) {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        <div className="card-panel p-6">
          <h1 className="text-2xl font-semibold">Nuevo Twister de entrenamiento</h1>
          <p className="mt-1 text-sm text-slate-400">3 jugadores · 500 fichas · ciegas 10/20 · niveles de 2 minutos (estructura configurable en el backend).</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {bots.map((b, i) => (
              <div key={i}>
                <label className="label">Estilo rival {String.fromCharCode(65 + i)}</label>
                <select className="input" value={b} onChange={(e) => setBots(bots.map((x, j) => (j === i ? e.target.value : x)))}>
                  {STYLES.map((s) => <option key={s} value={s}>{styleLabels[s] ?? s}</option>)}
                </select>
              </div>
            ))}
            <div>
              <label className="label">Premios (fracciones 1º, 2º…)</label>
              <input className="input" value={payouts} onChange={(e) => setPayouts(e.target.value)} placeholder="1.0  ó  0.8, 0.2" />
            </div>
            <div>
              <label className="label">Avance de niveles</label>
              <select className="input" value={levelMode} onChange={(e) => setLevelMode(e.target.value as "time" | "hands")}>
                <option value="time">Reloj virtual (25 s por mano)</option>
                <option value="hands">Por manos (6 por nivel)</option>
              </select>
            </div>
          </div>
          {error && <div className="mt-3 text-sm text-danger">{error}</div>}
          <button className="btn-primary mt-5 w-full" onClick={newGame} disabled={busy}>{busy ? "Creando…" : "Repartir"}</button>
        </div>
      </div>
    );
  }

  const hero = state.players[state.hero_seat];
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_400px]">
      <div className="space-y-3">
        <div className="card-panel flex flex-wrap items-center gap-2 px-3 py-2 text-xs text-slate-300">
          <span>Nivel {state.level.level} · {state.level.small_blind}/{state.level.big_blind}{state.level.ante ? ` · ante ${state.level.ante}` : ""}</span>
          {state.time_to_next_level !== null && <span className="text-slate-500">· siguiente nivel en {Math.ceil(state.time_to_next_level)} s</span>}
          {state.heads_up && <span className="tag bg-gold/20 text-gold">Heads-up</span>}
          <span className="ml-auto flex gap-1">
            <button className="btn-ghost !px-2 !py-1" disabled={busy} onClick={() => call(state.paused ? "resume" : "pause")}>{state.paused ? "▶ Reanudar" : "⏸ Pausar"}</button>
            <button className="btn-ghost !px-2 !py-1" disabled={busy || state.decisions === 0} onClick={() => call("undo")}>↩ Deshacer</button>
            <button className="btn-ghost !px-2 !py-1" disabled={busy || !state.hero_to_act} onClick={doCompare}>⇄ Comparar</button>
            <button className="btn-ghost !px-2 !py-1" onClick={() => setShowRec((v) => !v)}>{showRec ? "Ocultar ayuda" : "Mostrar ayuda"}</button>
          </span>
        </div>
        <div className="card-panel p-2">
          <PokerTable state={state} reveal={!state.hand_in_progress} />
        </div>
        {state.finished ? (
          <div className="card-panel p-4 text-center">
            <div className="text-lg font-semibold">Torneo terminado</div>
            <div className="mt-1 text-sm text-slate-300">
              {state.players.map((p) => `${p.name}: ${p.finish_place}º (${state.payouts[String(p.seat)] ?? 0} €)`).join(" · ")}
            </div>
            <button className="btn-primary mt-3" onClick={() => { setState(null); setRec(null); }}>Nuevo torneo</button>
          </div>
        ) : state.hero_to_act ? (
          <ActionBar legal={state.legal_actions} bb={state.level.big_blind} onAct={act} disabled={busy} suggested={showRec && rec ? { action: rec.action, amount: rec.amount } : null} />
        ) : (
          <div className="card-panel flex items-center justify-between p-3 text-sm text-slate-300">
            <span>{state.hand_in_progress ? "Esperando a los rivales…" : "Mano terminada."}</span>
            {!state.hand_in_progress && <button className="btn-primary" disabled={busy} onClick={() => call("deal")}>Siguiente mano</button>}
          </div>
        )}
        {state.last_result && !state.hand_in_progress && (
          <div className="card-panel p-3 text-sm">
            <div className="text-[11px] uppercase tracking-wider text-slate-500">Resultado mano #{state.last_result.hand_no}</div>
            {state.last_result.winners.map((w, i) => <div key={i}>🏆 {w.name} gana {w.amount}{w.hand ? ` con ${w.hand}` : ""}</div>)}
            {state.last_result.showdown.length > 0 && (
              <div className="mt-1 text-xs text-slate-400">{state.last_result.showdown.map((s) => `${s.name}: ${s.cards.join(" ")} (${s.hand})`).join(" · ")}</div>
            )}
          </div>
        )}
        {compare && (
          <div className="card-panel p-3 text-sm">
            <div className="mb-1 text-[11px] uppercase tracking-wider text-slate-500">Comparar alternativas (misma baraja, una repetición cada una; no es EV)</div>
            <table className="w-full"><tbody>
              {compare.map((c, i) => (
                <tr key={i} className="border-t border-ink-600/50">
                  <td className="py-1">{actionLabel(c.action.action)} {c.action.amount ?? ""}</td>
                  <td className="py-1 text-right font-mono">{c.error ? <span className="text-danger">{c.error}</span> : <span className={c.chip_delta! >= 0 ? "text-ok" : "text-danger"}>{c.chip_delta! >= 0 ? "+" : ""}{c.chip_delta}</span>}</td>
                  <td className="py-1 pl-2 text-right text-xs text-slate-400">{c.board?.join(" ")}</td>
                </tr>
              ))}
            </tbody></table>
          </div>
        )}
        {error && <div className="text-sm text-danger">{error}</div>}
        <div className="card-panel p-3 text-xs text-slate-400">
          <div className="mb-1 text-[11px] uppercase tracking-wider text-slate-500">Registro</div>
          {state.event_log.slice(-5).map((e, i) => <div key={i}>{e}</div>)}
          {state.actions.slice(-6).map((a, i) => <div key={`a${i}`} className="text-slate-500">{a.street}: {a.name} {a.action}{a.amount ? ` ${a.amount}` : ""}</div>)}
        </div>
      </div>
      <aside className="space-y-3">
        <div className="card-panel flex items-center justify-between p-3 text-sm">
          <span>Tu mano: <b className="text-accent">{hero.hole_cards.join(" ")}</b> · {hero.position}</span>
          <span className="text-slate-400">{hero.stack} fichas</span>
        </div>
        {showRec ? <AnalysisPanel rec={state.hero_to_act ? rec : null} bb={state.level.big_blind} loading={loadingRec} /> : <div className="card-panel p-4 text-sm text-slate-400">Ayuda oculta: decide primero y compara después con “Mostrar ayuda”.</div>}
      </aside>
    </div>
  );
}
