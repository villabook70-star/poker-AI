"use client";
import { useEffect, useRef, useState } from "react";
import { API_URL, wsUrl } from "@/lib/api";
import type { Recommendation } from "@/lib/types";
import { AnalysisPanel } from "@/components/AnalysisPanel";

const EXAMPLE = JSON.stringify({
  hero_cards: "As Kd", board: "", hero_position: "BB", hero_stack: 280, hero_committed: 20, pot: 550, to_call: 280, bb_size: 20, ante: 0, street: "preflop",
  players_remaining: 2, raise_count_preflop: 1,
  villains: [{ name: "Rival", position: "SB", stack: 0, committed: 530, all_in: true, preflop_action: "shove" }],
}, null, 2);

export default function LivePage() {
  const [payload, setPayload] = useState(EXAMPLE);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    const sock = new WebSocket(wsUrl("/api/live/ws"));
    sock.onopen = () => setConnected(true);
    sock.onclose = () => setConnected(false);
    sock.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.ok) { setRec(msg.recommendation); setLog((l) => [`✓ ${msg.recommendation.action} ${msg.recommendation.amount || ""} (${msg.recommendation.confidence})`, ...l].slice(0, 20)); }
      else setLog((l) => [`✗ ${msg.error}`, ...l].slice(0, 20));
    };
    ws.current = sock;
    return () => sock.close();
  }, []);

  function send() {
    try { JSON.parse(payload); ws.current?.send(payload); } catch (e) { setLog((l) => [`✗ JSON inválido: ${(e as Error).message}`, ...l]); }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
      <div className="space-y-4">
        <div className="card-panel p-5">
          <h1 className="text-xl font-semibold">Asistencia en directo · integración externa</h1>
          <p className="mt-1 text-sm text-slate-300">
            PokerMind no lee ni captura la pantalla de ningún cliente de póker (eso suele incumplir sus condiciones de uso y puede ser ilegal en tu jurisdicción).
            Ofrece una interfaz neutral: cualquier herramienta externa (entrada manual, un puente propio, un adaptador OCR escrito por ti) envía la situación y recibe la recomendación determinista.
          </p>
          <div className="mt-3 grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
            <div className="rounded-lg border border-ink-600/50 p-3"><b className="text-slate-200">HTTP</b><br /><code>POST {API_URL}/api/live/recommend</code><br />Cuerpo: la situación (mismo esquema que abajo). Respuesta: recomendación.</div>
            <div className="rounded-lg border border-ink-600/50 p-3"><b className="text-slate-200">WebSocket</b> <span className={`tag ${connected ? "bg-ok/15 text-ok" : "bg-danger/15 text-danger"}`}>{connected ? "conectado" : "desconectado"}</span><br /><code>{wsUrl("/api/live/ws")}</code><br />Cada mensaje JSON = una situación; cada respuesta = {"{ok, recommendation}"}.</div>
          </div>
          <label className="label mt-4">Situación (JSON)</label>
          <textarea className="input font-mono text-xs" rows={16} value={payload} onChange={(e) => setPayload(e.target.value)} />
          <button className="btn-primary mt-2" onClick={send} disabled={!connected}>Enviar por WebSocket</button>
        </div>
        <div className="card-panel p-4 text-xs">
          <div className="mb-1 text-[11px] uppercase tracking-wider text-slate-500">Registro</div>
          {log.length === 0 ? <div className="text-slate-500">Sin mensajes.</div> : log.map((l, i) => <div key={i} className="font-mono">{l}</div>)}
        </div>
      </div>
      <aside><AnalysisPanel rec={rec} /></aside>
    </div>
  );
}
