"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { RangeGrid } from "@/components/RangeGrid";
import { pct } from "@/lib/cards";

interface HuSolution { stack_bb: number; push: Record<string, number>; call: Record<string, number>; push_ev_bb: Record<string, number>; call_ev_bb: Record<string, number>; push_percent: number; call_percent: number; iterations: number; exploitability_bb: number; assumptions: string[]; }
interface BtnResult { hand: string; action: string; ev_shove_bb: number; ev_shove_icm: number; p_sb_call: number; p_bb_call: number; p_both_fold: number; equity_vs_sb_call: number; equity_vs_bb_call: number; sb_call_range_percent: number; bb_call_range_percent: number; assumptions: string[]; }

export default function PushFoldPage() {
  const [stack, setStack] = useState(10);
  const [ante, setAnte] = useState(0);
  const [sol, setSol] = useState<HuSolution | null>(null);
  const [hand, setHand] = useState("A5s");
  const [btn, setBtn] = useState({ hand: "A5s", btn: 200, sb: 500, bb: 800, bbSize: 20, ante: 0, payouts: "1.0" });
  const [btnRes, setBtnRes] = useState<BtnResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<HuSolution>(`/api/analysis/pushfold/hu?stack_bb=${stack}&ante_bb=${ante}`).then((s) => { setSol(s); setError(null); }).catch((e) => setError((e as Error).message));
  }, [stack, ante]);

  async function runBtn() {
    try {
      setBtnRes(await api.post<BtnResult>("/api/analysis/pushfold/btn", { hand: btn.hand, stacks: [btn.btn, btn.sb, btn.bb], bb_size: btn.bbSize, ante: btn.ante, payouts: btn.payouts.split(",").map((x) => parseFloat(x)) }));
      setError(null);
    } catch (e) { setError((e as Error).message); }
  }

  const h = hand.trim();
  return (
    <div className="space-y-4">
      <div className="card-panel p-5">
        <h1 className="text-xl font-semibold">Push/Fold heads-up · equilibrio de Nash</h1>
        <p className="mt-1 text-xs text-slate-400">
          Calculado localmente por juego ficticio sobre el juego restringido (SB: all-in o fold; BB: call o fold) con la matriz de equity 169×169 (Monte Carlo, 20.000 muestras por pareja).
          Es un equilibrio real del juego restringido, no una tabla copiada. Heads-up el ICM es lineal, así que la decisión no depende de la estructura de premios.
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-4">
          <div><label className="label">Stack efectivo (bb)</label><input type="range" min={2} max={25} step={0.5} value={stack} onChange={(e) => setStack(Number(e.target.value))} className="w-56 accent-teal-300" /><div className="font-mono text-sm">{stack} bb</div></div>
          <div><label className="label">Ante (bb)</label><input className="input w-24" type="number" step={0.05} min={0} max={0.5} value={ante} onChange={(e) => setAnte(Number(e.target.value))} /></div>
          <div><label className="label">Consultar mano</label><input className="input w-24" value={hand} onChange={(e) => setHand(e.target.value)} placeholder="K7o" /></div>
        </div>
        {error && <div className="mt-2 text-sm text-danger">{error}</div>}
        {sol && (
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div>
              <div className="mb-1 flex items-center gap-2 text-sm"><b>SB empuja</b> <span className="tag bg-violet-400/15 text-violet-300">{sol.push_percent}% de manos</span></div>
              <RangeGrid grid={sol.push} />
              {sol.push_ev_bb[h] !== undefined && <div className="mt-2 text-sm">{h}: push {pct(sol.push[h] ?? 0, 0)} · EV(push) <span className="font-mono">{sol.push_ev_bb[h].toFixed(3)} bb</span> vs EV(fold) <span className="font-mono">{(-0.5 - ante).toFixed(2)} bb</span></div>}
            </div>
            <div>
              <div className="mb-1 flex items-center gap-2 text-sm"><b>BB paga</b> <span className="tag bg-violet-400/15 text-violet-300">{sol.call_percent}% de manos</span></div>
              <RangeGrid grid={sol.call} />
              {sol.call_ev_bb[h] !== undefined && <div className="mt-2 text-sm">{h}: call {pct(sol.call[h] ?? 0, 0)} · EV(call) <span className="font-mono">{sol.call_ev_bb[h].toFixed(3)} bb</span> vs EV(fold) <span className="font-mono">{(-1 - ante).toFixed(2)} bb</span></div>}
            </div>
          </div>
        )}
        {sol && <div className="mt-3 text-[11px] text-slate-500">Iteraciones: {sol.iterations} · explotabilidad residual {sol.exploitability_bb} bb · {sol.assumptions.join(" ")}</div>}
      </div>

      <div className="card-panel p-5">
        <h2 className="text-lg font-semibold">Open-shove desde el botón (3 jugadores) · estimación</h2>
        <p className="mt-1 text-xs text-slate-400">EV de ir all-in desde BTN contra rangos de call asumidos (por defecto, los rangos de call Nash HU al stack efectivo de cada rival) con ICM Malmuth-Harville. No es un equilibrio a tres bandas: se etiqueta como estimación.</p>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-7">
          <div><label className="label">Mano</label><input className="input" value={btn.hand} onChange={(e) => setBtn({ ...btn, hand: e.target.value })} /></div>
          <div><label className="label">Stack BTN</label><input className="input" type="number" value={btn.btn} onChange={(e) => setBtn({ ...btn, btn: Number(e.target.value) })} /></div>
          <div><label className="label">Stack SB</label><input className="input" type="number" value={btn.sb} onChange={(e) => setBtn({ ...btn, sb: Number(e.target.value) })} /></div>
          <div><label className="label">Stack BB</label><input className="input" type="number" value={btn.bb} onChange={(e) => setBtn({ ...btn, bb: Number(e.target.value) })} /></div>
          <div><label className="label">Ciega grande</label><input className="input" type="number" value={btn.bbSize} onChange={(e) => setBtn({ ...btn, bbSize: Number(e.target.value) })} /></div>
          <div><label className="label">Ante</label><input className="input" type="number" value={btn.ante} onChange={(e) => setBtn({ ...btn, ante: Number(e.target.value) })} /></div>
          <div><label className="label">Premios</label><input className="input" value={btn.payouts} onChange={(e) => setBtn({ ...btn, payouts: e.target.value })} /></div>
        </div>
        <button className="btn-primary mt-3" onClick={runBtn}>Calcular</button>
        {btnRes && (
          <div className="mt-4 text-sm">
            <div className="text-xl font-semibold">{btnRes.hand}: <span className={btnRes.action === "push" ? "text-accent" : "text-danger"}>{btnRes.action === "push" ? "ALL-IN" : "FOLD"}</span> <span className="tag bg-warn/15 text-warn">estimación</span></div>
            <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <S l="EV all-in (fichas)" v={`${btnRes.ev_shove_bb >= 0 ? "+" : ""}${btnRes.ev_shove_bb.toFixed(3)} bb`} />
              <S l="ΔEV ICM" v={`${btnRes.ev_shove_icm >= 0 ? "+" : ""}${(btnRes.ev_shove_icm * 100).toFixed(2)}% premio`} />
              <S l="P(SB paga) / rango" v={`${pct(btnRes.p_sb_call, 0)} / ${btnRes.sb_call_range_percent}%`} />
              <S l="P(BB paga) / rango" v={`${pct(btnRes.p_bb_call, 0)} / ${btnRes.bb_call_range_percent}%`} />
              <S l="Ambos foldean" v={pct(btnRes.p_both_fold, 0)} />
              <S l="Equity vs call SB" v={pct(btnRes.equity_vs_sb_call)} />
              <S l="Equity vs call BB" v={pct(btnRes.equity_vs_bb_call)} />
            </div>
            <ul className="mt-3 space-y-0.5 text-[11px] text-slate-500">{btnRes.assumptions.map((a, i) => <li key={i}>• {a}</li>)}</ul>
          </div>
        )}
      </div>
    </div>
  );
}
function S({ l, v }: { l: string; v: string }) { return <div><div className="text-[10px] uppercase tracking-wider text-slate-500">{l}</div><div className="font-mono">{v}</div></div>; }
