"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Profile, StatInfo } from "@/lib/types";
import { pct } from "@/lib/cards";

const STATS: { key: keyof Profile; label: string }[] = [
  { key: "vpip", label: "VPIP" }, { key: "pfr", label: "PFR" }, { key: "three_bet", label: "3-bet" },
  { key: "fold_to_three_bet", label: "Fold a 3-bet" }, { key: "cbet", label: "C-bet" }, { key: "fold_to_cbet", label: "Fold a c-bet" }, { key: "wtsd", label: "WTSD" },
];

function StatBar({ s }: { s: StatInfo }) {
  if (s.value === null) return <span className="text-xs text-slate-500">sin datos</span>;
  const [lo, hi] = s.ci95;
  return (
    <div className="w-full">
      <div className="relative h-2 w-full rounded bg-ink-600">
        <div className="absolute h-2 rounded bg-accent/30" style={{ left: `${lo * 100}%`, width: `${(hi - lo) * 100}%` }} />
        <div className="absolute top-[-2px] h-3 w-[2px] bg-accent" style={{ left: `${s.value * 100}%` }} />
      </div>
      <div className="mt-0.5 font-mono text-[11px] text-slate-300">{pct(s.value, 0)} <span className="text-slate-500">[{pct(lo, 0)}–{pct(hi, 0)}] n={s.n}</span></div>
    </div>
  );
}

export default function ProfilesPage() {
  const [list, setList] = useState<Profile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", hands: 0, vpip: "", vpip_n: 0, pfr: "", pfr_n: 0, three_bet: "", three_bet_n: 0, fold_to_three_bet: "", fold_to_three_bet_n: 0, fold_to_cbet: "", fold_to_cbet_n: 0, aggressive_actions: 0, passive_actions: 0, notes: "" });

  const load = () => api.get<Profile[]>("/api/profiles").then(setList).catch((e) => setError((e as Error).message));
  useEffect(() => { load(); }, []);

  async function save() {
    const stat = (v: string, n: number) => (v.trim() === "" ? undefined : { value: parseFloat(v) > 1 ? parseFloat(v) / 100 : parseFloat(v), n });
    try {
      await api.post("/api/profiles", { name: form.name, hands: form.hands, vpip: stat(form.vpip, form.vpip_n), pfr: stat(form.pfr, form.pfr_n), three_bet: stat(form.three_bet, form.three_bet_n), fold_to_three_bet: stat(form.fold_to_three_bet, form.fold_to_three_bet_n), fold_to_cbet: stat(form.fold_to_cbet, form.fold_to_cbet_n), aggressive_actions: form.aggressive_actions, passive_actions: form.passive_actions, notes: form.notes });
      setError(null); load();
    } catch (e) { setError((e as Error).message); }
  }

  const f = (k: keyof typeof form, v: string | number) => setForm({ ...form, [k]: v });
  return (
    <div className="grid gap-4 lg:grid-cols-[380px_minmax(0,1fr)]">
      <div className="card-panel p-5">
        <h1 className="text-xl font-semibold">Perfil de rival</h1>
        <p className="mt-1 text-xs text-slate-400">Introduce frecuencia (0–1 o %) y número de oportunidades. Con muestras pequeñas el intervalo de confianza será amplio y la app no asignará un estilo.</p>
        <div className="mt-3 space-y-2">
          <div><label className="label">Nombre</label><input className="input" value={form.name} onChange={(e) => f("name", e.target.value)} /></div>
          <div><label className="label">Manos observadas</label><input className="input" type="number" value={form.hands} onChange={(e) => f("hands", Number(e.target.value))} /></div>
          {(["vpip", "pfr", "three_bet", "fold_to_three_bet", "fold_to_cbet"] as const).map((k) => (
            <div key={k} className="grid grid-cols-2 gap-2">
              <div><label className="label">{STATS.find((s) => s.key === k)?.label}</label><input className="input" placeholder="0.45" value={form[k]} onChange={(e) => f(k, e.target.value)} /></div>
              <div><label className="label">oportunidades</label><input className="input" type="number" value={form[`${k}_n` as keyof typeof form] as number} onChange={(e) => f(`${k}_n` as keyof typeof form, Number(e.target.value))} /></div>
            </div>
          ))}
          <div className="grid grid-cols-2 gap-2">
            <div><label className="label">Bets/raises postflop</label><input className="input" type="number" value={form.aggressive_actions} onChange={(e) => f("aggressive_actions", Number(e.target.value))} /></div>
            <div><label className="label">Calls postflop</label><input className="input" type="number" value={form.passive_actions} onChange={(e) => f("passive_actions", Number(e.target.value))} /></div>
          </div>
          <div><label className="label">Notas / tendencias de apuesta</label><textarea className="input" rows={2} value={form.notes} onChange={(e) => f("notes", e.target.value)} /></div>
          <button className="btn-primary w-full" onClick={save} disabled={!form.name.trim()}>Guardar</button>
          {error && <div className="text-sm text-danger">{error}</div>}
        </div>
      </div>
      <div className="space-y-3">
        {list.length === 0 && <div className="card-panel p-5 text-sm text-slate-400">Sin perfiles. Créalos aquí o impórtalos desde historiales.</div>}
        {list.map((p) => (
          <div key={p.name} className="card-panel p-4">
            <div className="flex flex-wrap items-center gap-2">
              <b className="text-lg">{p.name}</b>
              <span className="tag bg-ink-600 text-slate-300">{p.hands} manos</span>
              <span className={`tag ${p.style.startsWith("insuficiente") ? "bg-warn/15 text-warn" : "bg-accent/15 text-accent"}`}>{p.style}</span>
              <span className="tag bg-ink-600 text-slate-300">confianza {p.confidence}</span>
              {p.aggression_factor !== null && <span className="tag bg-ink-600 text-slate-300">AF {p.aggression_factor}</span>}
              <button className="btn-danger ml-auto !px-2 !py-1" onClick={() => api.del(`/api/profiles/${encodeURIComponent(p.name)}`).then(load)}>Eliminar</button>
            </div>
            {p.warning && <div className="mt-1 text-xs text-warn">⚠ {p.warning}</div>}
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {STATS.map((s) => (
                <div key={s.key}><div className="text-[10px] uppercase tracking-wider text-slate-500">{s.label}</div><StatBar s={p[s.key] as StatInfo} /></div>
              ))}
            </div>
            <div className="mt-2 text-[11px] text-slate-500">
              Tamaños de apuesta: {Object.entries(p.bet_sizes).map(([k, v]) => `${k}: ${v}`).join(" · ")}
              {p.notes && <> · Notas: {p.notes}</>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
