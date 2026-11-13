"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Inicio" },
  { href: "/simulator", label: "Simulador" },
  { href: "/analyze", label: "Analizar" },
  { href: "/pushfold", label: "Push/Fold" },
  { href: "/profiles", label: "Rivales" },
  { href: "/import", label: "Importar" },
  { href: "/live", label: "En directo" },
];

export function Nav() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-20 border-b border-ink-700/70 bg-ink-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="inline-block h-6 w-6 rounded-md bg-accent shadow-glow" />
          <span>PokerMind <span className="text-accent">AI</span></span>
        </Link>
        <nav className="ml-auto flex gap-1 overflow-x-auto text-sm">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className={`whitespace-nowrap rounded-md px-3 py-1.5 transition ${path === l.href ? "bg-ink-700 text-white" : "text-slate-400 hover:text-white"}`}>
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
