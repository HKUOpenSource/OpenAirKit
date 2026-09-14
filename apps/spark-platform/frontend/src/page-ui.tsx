import type { LucideIcon } from "lucide-react";
import { Badge, names, text, value } from "./components";
import type { Observation } from "./types";

export function PageIntro({ title, description, icon: Icon }: { title: string; description: string; icon: LucideIcon }) {
  return <section className="page-intro"><div><h2>{title}</h2><p>{description}</p></div><Icon /></section>;
}

export function StatusSummary({ state, title, reason, updated }: { state: string; title: string; reason: string; updated: string }) {
  return <section className={`status-summary state-${state}`}>
    <div className="status-copy"><span className={`status-dot ${state}`} /><div><h2>{title}</h2><p>{reason}</p></div></div>
    <time className="updated">Updated {updated}</time>
  </section>;
}

export function SummaryItem({ icon: Icon, label, children }: { icon: LucideIcon; label: string; children: React.ReactNode }) {
  return <div><Icon /><span>{label}<strong>{children}</strong></span></div>;
}

export function DetailRows({ values }: { values: Record<string, unknown> }) {
  return <dl className="detail-list">{Object.entries(values).map(([key, item]) => <div key={key}>
    <dt>{names[key] || text(key)}</dt><dd className="mono">{item == null || item === "" ? "—" : typeof item === "object" ? JSON.stringify(item) : String(item)}</dd>
  </div>)}</dl>;
}

export function MetricValue({ observation }: { observation?: Observation }) {
  return <>{value(observation)}</>;
}

export function EvidenceState({ state, reason }: { state: string; reason?: unknown }) {
  return <span className="evidence-state"><Badge state={state} /><small>{reason ? text(String(reason)) : "No supporting detail"}</small></span>;
}
