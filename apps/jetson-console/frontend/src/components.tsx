import { Activity, Check, Download, Play, Square } from "lucide-react";
import { api, download, number, Obj, speed, terminal, when } from "./api";

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
  return <section className="job-panel"><div className="section-heading"><div><h2>{job.kind === "setup" ? "Device setup" : job.kind === "recover" ? "Recovery" : "Speed test"}</h2>
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

export function SpeedGauge({ job, start, stop, disabled }: { job: Obj | null; start: () => void; stop: () => void; disabled: boolean }) {
  const running = Boolean(job && !terminal(job));
  const bps = running ? job?.live_sample?.bps : null;
  const mbps = typeof bps === "number" ? bps / 1e6 : null;
  const progress = mbps === null ? 0 : Math.min(100, Math.log10(1 + mbps) / 2.2 * 100);
  return <div className="gauge" data-testid="speed-gauge"><svg viewBox="0 0 360 245" role="img" aria-label="Live throughput gauge"><path className="gauge-track" d="M55 210A130 130 0 1 1 305 210" pathLength="100" />
    <path className="gauge-progress" d="M55 210A130 130 0 1 1 305 210" pathLength="100" strokeDasharray={`${progress} 100`} /><text x="45" y="238">0</text><text x="170" y="24">25</text><text x="300" y="238">150+</text></svg>
    <div className="gauge-center">{running ? <><strong>{number(mbps)}</strong><span>{job?.phase} Mbps</span><button className="quiet" onClick={stop}><Square size={14} /> Stop</button></> : <><button className="go" onClick={start} disabled={disabled}>GO</button><span>Start speed test</span></>}</div></div>;
}

export function ResultsTable({ jobs }: { jobs: Obj[] }) {
  return <div className="table-wrap"><table><thead><tr><th>Started</th><th>Download</th><th>Upload</th><th>Result</th></tr></thead><tbody>{jobs.map(job => <tr key={job.id}><td>{when(job.created_at)}</td><td>{speed(job.result?.download?.bps)} Mbps</td><td>{speed(job.result?.upload?.bps)} Mbps</td><td><Badge state={job.state} />{job.error ? <small className="failure">{job.error}</small> : null}</td></tr>)}</tbody></table>{!jobs.length ? <Empty /> : null}</div>;
}
