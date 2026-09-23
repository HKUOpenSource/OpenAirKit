import { Activity, Check, Download, Play, Square } from "lucide-react";
import { api, download, number, Obj, terminal, when } from "./api";

export function Badge({ state = "unknown" }: { state?: string }) {
  return <span className={"badge " + state}><i />{state.replaceAll("_", " ")}</span>;
}

export function Empty({ children = "No records in this window" }: { children?: React.ReactNode }) {
  return <p className="empty">{children}</p>;
}

export function Fields({ items }: { items: [string, React.ReactNode][] }) {
  return <dl className="fields">{items.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value ?? "--"}</dd></div>)}</dl>;
}

export function MiniChart({ samples, field, label, unit }: { samples: Obj[]; field: (sample: Obj) => number | null; label: string; unit: string }) {
  const values = samples.map(field);
  const valid = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const minimum = valid.length ? Math.min(...valid) : 0;
  const maximum = valid.length ? Math.max(...valid) : 1;
  const span = Math.max(1, maximum - minimum);
  let current = "";
  const paths: string[] = [];
  values.forEach((value, index) => {
    if (value === null || !Number.isFinite(value)) { if (current) paths.push(current); current = ""; return; }
    const x = 18 + index / Math.max(1, values.length - 1) * 524;
    const y = 102 - (value - minimum) / span * 76;
    current += (current ? " L" : "M") + `${x},${y}`;
  });
  if (current) paths.push(current);
  return <section className="chart-panel"><div className="section-heading"><div><h2>{label}</h2><small>{unit}</small></div><strong>{valid.length ? number(valid.at(-1)) : "--"}</strong></div>
    {valid.length ? <svg viewBox="0 0 560 126" role="img" aria-label={label + " history"}><path className="grid-line" d="M18 26H542M18 64H542M18 102H542" />
      {paths.map((path, index) => <path className="data-line" key={index} d={path} />)}</svg> : <Empty>No current samples</Empty>}</section>;
}

export function JobPanel({ job, refresh, error }: { job: Obj | null; refresh: () => void; error: (value: string) => void }) {
  if (!job) return <section><Empty>No task has been created</Empty></section>;
  async function perform(action: "run" | "cancel") {
    try { await api(`jobs/${job!.id}/${action}`, action === "run" ? { confirmed: true } : {}); refresh(); }
    catch (reason) { error(String(reason)); }
  }
  return <section className="job-panel"><div className="section-heading"><div><h2>{job.kind === "setup" ? "Device setup" : "Recovery"}</h2>
    <small>Task {job.id.slice(0, 8)} · {when(job.created_at)}</small></div><Badge state={job.state} /></div>
    <progress value={job.progress || 0} max="100" aria-label="Task progress" />
    <ol className="steps">{job.steps.map((step: Obj) => <li key={step.id}><span className={step.state}>{step.state === "complete" ? <Check size={14} /> : <Activity size={14} />}</span>
      <div><b>{step.id}</b><small>{step.error || step.state}</small></div></li>)}</ol>
    {job.error ? <p className="alert error" role="alert">{job.error}</p> : null}
    {job.cleanup ? <p className="alert">Cleanup: {job.cleanup.error || job.cleanup.reason || JSON.stringify(job.cleanup)}</p> : null}
    <div className="actions">{["ready", "paused"].includes(job.state) ? <button className="primary" onClick={() => perform("run")}><Play size={15} />{job.state === "paused" ? "Run next step" : "Confirm and run"}</button> : null}
      {!terminal(job) ? <button onClick={() => perform("cancel")}><Square size={15} />Cancel</button> : null}
      <button onClick={() => download(`jobs/${job.id}`, `aoc-jetson-task-${job.id}.json`).catch(reason => error(String(reason)))}><Download size={15} />Report</button></div>
  </section>;
}
