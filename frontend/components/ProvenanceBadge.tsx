import { provenanceClass, provenanceLabel } from "@/lib/cards";

export function ProvenanceBadge({ type }: { type: string }) {
  return <span className={`tag ${provenanceClass(type)}`}>{provenanceLabel(type)}</span>;
}

export function ConfidenceBadge({ level, score }: { level: string; score?: number }) {
  const cls = level === "alta" ? "bg-ok/15 text-ok" : level === "media" ? "bg-warn/15 text-warn" : "bg-danger/15 text-danger";
  return (
    <span className={`tag ${cls}`}>
      confianza {level}
      {score !== undefined ? ` · ${(score * 100).toFixed(0)}%` : ""}
    </span>
  );
}
