import { Activity, ArrowLeft, Download, Play, RotateCcw, Settings, Square, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { Badge, Details, Metrics, Trend, names, text, when } from "../components";
import { PageIntro } from "../page-ui";
import type { PageProps } from "../page-types";
import type { Component, ControlTask, Snapshot } from "../types";

export function ComponentDetailPage({ snapshot, refresh }: PageProps) {
  const { id = "" } = useParams();
  const [stored, setStored] = useState<Component | null>(null);
  const [error, setError] = useState("");
  const component = [...(snapshot.components || []), ...(snapshot.links || [])].find(item => item.id === id) || (stored?.id === id ? stored : null);
  useEffect(() => {
    const controller = new AbortController();
    api<Component>(`components/${encodeURIComponent(id)}`, {signal: controller.signal}).then(item => { setStored(item); setError(""); })
      .catch(exc => { if (exc.name !== "AbortError") setError("Component not found or outside the retention window"); });
    return () => controller.abort();
  }, [id, refresh]);
  return <div className="spark-page"><Link className="back-link" to="/core"><ArrowLeft />Core Network</Link>
    {error && <div className="connection-banner" role="alert">{error}</div>}
    {component && <><section className="page-intro"><div><h2>{component.name}</h2><p>Runtime, business health, evidence, and retained metrics.</p></div><Activity /></section>
      <section className="section-frame detail-panel"><header><h2>Component details</h2><Badge state={component.status && component.status !== "ok" ? component.status : component.business_health || component.health || component.state} /></header><Details values={{kind: text(component.kind), runtime_state: text(component.state), evidence_time: when(component.observed_at), ...component.details}} /></section>
      <section className="section-frame metric-panel"><header><h2>Current metrics</h2></header><Metrics items={component.metrics} /></section>
      <div className="chart-grid">{component.metrics.filter(metric => typeof metric.value === "number" && Number.isFinite(metric.value)).slice(0, 8).map(metric => <Trend key={metric.name} entity={id} metric={metric.name} refresh={refresh} />)}</div>
    </>}
  </div>;
}

export function HistoryPage({ snapshot, stack, refresh }: PageProps) {
  const options = useMemo(() => [
    ...[...(snapshot.components || []), ...(snapshot.links || [])].filter(item => item.stack === stack || item.id === "spark").map(item => ({...item, apiKind: "components"})),
    ...(snapshot.devices || []).filter(item => item.stack === stack).map(item => ({...item, name: item.identity, apiKind: "devices"})),
  ], [snapshot, stack]);
  const [entity, setEntity] = useState("spark");
  const [hours, setHours] = useState(1);
  const [metric, setMetric] = useState("cpu_usage");
  const current = options.find(item => item.id === entity) || options[0];
  const available = [...new Set((current?.metrics || []).filter(item => typeof item.value === "number" || ["ratio", "byte", "bit/s", "cores", "C", "seconds", "dB", "count"].includes(item.unit)).map(item => item.name))];
  const selectedMetric = available.includes(metric) ? metric : available[0] || "";
  return <div className="spark-page">
    <PageIntro title="Metric history" description="Retained component and device observations, aggregated for the selected time window." icon={Activity} />
    <div className="page-actions"><Link className="secondary-button" to="/events">Back to events</Link></div>
    <div className="filter-bar">
      <label><span>Component or device</span><select aria-label="History component" value={current?.id || ""} onChange={event => setEntity(event.target.value)}>{options.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label><span>Metric</span><select aria-label="History metric" value={selectedMetric} disabled={!available.length} onChange={event => setMetric(event.target.value)}>{!available.length && <option value="">No numeric metrics</option>}{available.map(item => <option key={item} value={item}>{names[item] || text(item)}</option>)}</select></label>
      <label><span>Time</span><select aria-label="Metric time range" value={hours} onChange={event => setHours(Number(event.target.value))}><option value={1}>One hour</option><option value={24}>One day</option><option value={168}>Seven days</option></select></label>
    </div>
    {selectedMetric && current && <Trend key={`${current.id}:${selectedMetric}:${hours}`} kind={current.apiKind} entity={current.id} metric={selectedMetric} hours={hours} refresh={refresh} />}
  </div>;
}

export function DiagnosticsPage({ snapshot, stack }: PageProps) {
  const [downloadError, setDownloadError] = useState("");
  async function download() {
    try {
      const bundle = await api<Snapshot>("diagnostics");
      const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], {type: "application/json"}));
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = "agentic-ocudu-spark-diagnostics.json"; anchor.click(); URL.revokeObjectURL(url); setDownloadError("");
    } catch { setDownloadError("Unable to create the redacted diagnostic export"); }
  }
  const observations = snapshot.observations.filter(item => (item.entity === stack || item.entity.startsWith(`${stack}:`) || item.entity === "spark") && (item.status !== "ok" || item.reason));
  return <div className="spark-page"><PageIntro title="Diagnostics" description="Collector evidence, unavailable fields, and a redacted support export." icon={Settings} />
    <div className="page-actions"><button className="secondary-button" onClick={download}><Download />Download redacted snapshot</button></div>
    {downloadError && <div className="connection-banner" role="alert">{downloadError}</div>}
    <section className="section-frame detail-panel"><header><h2>Host evidence</h2></header><Details values={snapshot.components?.find(item => item.id === "spark")?.details || {host_evidence: "unavailable"}} /></section>
    <section className="table-section"><header><h2>Evidence requiring attention</h2><span className="section-meta">{observations.length} records</span></header><div className="diagnostics">{observations.map(item => <div key={item.entity + item.name}><span>{item.entity} / {names[item.name] || text(item.name)}</span><Badge state={item.status} /><span title={item.reason || ""}>{text(item.reason || "")}</span></div>)}{!observations.length && <p className="empty">No unavailable or qualified evidence</p>}</div></section>
    <details className="inline-disclosure"><summary>Optional ext-DN ICMP diagnostics · measured from Spark</summary>{snapshot.devices?.filter(item => item.stack === stack && item.reachability?.observed_at).map(item => <div key={item.id}><h3><Link to={`/devices/${encodeURIComponent(item.id)}`}>{item.identity}</Link></h3><Details values={{measurement_point: "Spark ext-DN container", target: "UE address reported by Open5GS", result: text(item.reachability?.state || "unknown"), reason: text(item.reachability?.reason || ""), sampled_at: when(item.reachability?.observed_at)}} /></div>)}{!snapshot.devices?.some(item => item.stack === stack && item.reachability?.observed_at) && <p className="empty">No diagnostic samples. ICMP probing is disabled by default.</p>}</details>
  </div>;
}

export function OperationsPage({ csrf, refresh }: PageProps) {
  const [items, setItems] = useState<ControlTask[]>([]);
  const [selected, setSelected] = useState<ControlTask["action"] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const active = items.find(item => ["queued", "running", "cancel_requested"].includes(item.state));
  useEffect(() => {
    let alive = true;
    const load = () => api<{items: ControlTask[]}>("control?limit=50").then(result => { if (alive) { setItems(result.items); setError(""); } }).catch(() => { if (alive) setError("Unable to load stack control history"); });
    load(); const timer = window.setInterval(load, active ? 1000 : 5000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [refresh, active?.id, active?.state]);
  async function submit() {
    if (!selected) return; setBusy(true);
    try { const task = await api<ControlTask>("control", {method: "POST", headers: {"X-CSRF-Token": csrf}, body: JSON.stringify({action: selected, confirmation: true})}); setItems(current => [task, ...current]); setSelected(null); setError(""); }
    catch (exc) { setError(text((exc as Error).message)); } finally { setBusy(false); }
  }
  async function cancel(id: string) {
    try { const task = await api<ControlTask>(`control/${id}/cancel`, {method: "POST", headers: {"X-CSRF-Token": csrf}}); setItems(current => current.map(item => item.id === id ? task : item)); }
    catch (exc) { setError(text((exc as Error).message)); }
  }
  return <div className="spark-page"><PageIntro title="Stack operations" description="Bounded control for the independent Agentic-OCUDU protocol stack." icon={Settings} />
    <section className="section-frame operations-panel"><header><h2>Independent stack control</h2><span className="section-meta">OCUDU · Open5GS · data only</span></header>
      <p>Start, stop, or restart only the Agentic-OCUDU stack. The monitoring platform remains available after a stack stop.</p>
      <div className="control-actions"><button disabled={Boolean(active)} onClick={() => setSelected("start")}><Play />Start</button><button disabled={Boolean(active)} onClick={() => setSelected("stop")}><Square />Stop</button><button disabled={Boolean(active)} onClick={() => setSelected("restart")}><RotateCcw />Restart</button></div>
      {selected && <div className="confirm-operation" role="dialog" aria-label="Confirm stack operation"><div><strong>Confirm {selected}</strong><p>This interrupts active UE sessions. Jetson must reconnect after the radio returns.</p></div><button onClick={() => setSelected(null)}>Back</button><button className="primary-button" disabled={busy} onClick={submit}>{busy ? "Submitting…" : "Confirm"}</button></div>}
      {error && <div className="connection-banner" role="alert">{error}</div>}
    </section>
    <section className="table-section"><header><h2>Operation history</h2><span className="section-meta">30-day retention</span></header>
      <div className="operation-list">{items.map(item => <div className={`control-task ${item.state}`} key={item.id}><div><strong>{text(item.action)} · <Badge state={item.state} /></strong><small>{when(item.updated_at)}</small></div><ol>{item.steps.map(step => <li key={step.name}><span>{text(step.name)}</span><Badge state={step.state} /></li>)}</ol>{item.error && <p>{text(item.error)}</p>}{["queued", "running"].includes(item.state) && <button onClick={() => cancel(item.id)}><XCircle />Cancel at next safe boundary</button>}</div>)}{!items.length && <p className="empty">No stack operations recorded</p>}</div>
    </section>
  </div>;
}
