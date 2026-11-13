"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, API_URL } from "@/lib/api";

const features = [
  { href: "/simulator", title: "Simulador en vivo", desc: "Mesa Twister de 3 jugadores con bots configurables, recomendación y EV en cada decisión, pausa, deshacer y comparar alternativas." },
  { href: "/analyze", title: "Analizar una situación", desc: "Describe cartas, bote, stacks y acciones: equity exacta o Monte Carlo, pot odds y recomendación con nivel de confianza." },
  { href: "/pushfold", title: "Push/Fold Nash", desc: "Equilibrio heads-up calculado localmente (juego restringido) y estimación de open-shove en el botón con ICM." },
  { href: "/profiles", title: "Perfiles de rivales", desc: "VPIP, PFR, 3-bet, folds, agresividad y tamaños de apuesta con intervalos de confianza según la muestra." },
  { href: "/import", title: "Importar partidas", desc: "Historiales PokerStars o JSON genérico: reconstrucción mano a mano, errores y oportunidades de mejora." },
  { href: "/live", title: "Asistencia en directo", desc: "API y WebSocket neutrales para integrar recomendaciones con herramientas externas." },
];

export default function Home() {
  const [status, setStatus] = useState<{ ok: boolean; matrix?: boolean; claude?: boolean; error?: string } | null>(null);
  useEffect(() => {
    api.get<{ equity_matrix: boolean; claude_available: boolean }>("/api/analysis/status")
      .then((s) => setStatus({ ok: true, matrix: s.equity_matrix, claude: s.claude_available }))
      .catch((e) => setStatus({ ok: false, error: (e as Error).message }));
  }, []);
  return (
    <div className="space-y-8">
      <section className="card-panel relative overflow-hidden p-8">
        <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-accent/10 blur-3xl" />
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Entrena Twister Poker con <span className="text-accent">matemáticas verificables</span>
        </h1>
        <p className="mt-3 max-w-2xl text-slate-300">
          PokerMind AI separa con claridad lo exacto (evaluación de manos, enumeración, pot odds), lo estimado (Monte Carlo con error estándar),
          lo que proviene de un equilibrio Nash push/fold y lo heurístico. Nunca presenta una heurística como jugada óptima.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link href="/simulator" className="btn-primary">Empezar a entrenar</Link>
          <Link href="/analyze" className="btn-ghost">Analizar una mano</Link>
        </div>
        <div className="mt-5 flex flex-wrap gap-2 text-xs">
          {status === null && <span className="tag bg-ink-600 text-slate-300">Conectando con {API_URL}…</span>}
          {status?.ok && (
            <>
              <span className="tag bg-ok/15 text-ok">Backend conectado</span>
              <span className={`tag ${status.matrix ? "bg-ok/15 text-ok" : "bg-danger/15 text-danger"}`}>
                Matriz de equity 169×169 {status.matrix ? "cargada" : "ausente (ejecuta scripts/build_equity_matrix.py)"}
              </span>
              <span className={`tag ${status.claude ? "bg-ok/15 text-ok" : "bg-ink-600 text-slate-300"}`}>
                Claude API {status.claude ? "activa" : "no configurada (explicaciones deterministas)"}
              </span>
            </>
          )}
          {status && !status.ok && <span className="tag bg-danger/15 text-danger">Backend no disponible en {API_URL}: {status.error}</span>}
        </div>
      </section>
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((f) => (
          <Link key={f.href} href={f.href} className="card-panel group p-5 transition hover:border-accent/50">
            <div className="text-lg font-medium group-hover:text-accent">{f.title}</div>
            <p className="mt-1 text-sm text-slate-400">{f.desc}</p>
          </Link>
        ))}
      </section>
      <section className="card-panel p-5 text-sm text-slate-300">
        <div className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">Leyenda de procedencia</div>
        <div className="flex flex-wrap gap-3">
          <span><span className="tag bg-ok/15 text-ok">Exacto</span> enumeración completa o aritmética</span>
          <span><span className="tag bg-sky-400/15 text-sky-300">Monte Carlo</span> estimación con error estándar</span>
          <span><span className="tag bg-violet-400/15 text-violet-300">Nash push/fold</span> equilibrio del juego restringido</span>
          <span><span className="tag bg-warn/15 text-warn">Heurístico</span> regla práctica o supuesto</span>
        </div>
      </section>
    </div>
  );
}
