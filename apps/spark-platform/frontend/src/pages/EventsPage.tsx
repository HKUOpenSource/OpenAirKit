import { RefreshCw, ScrollText } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Badge, text, when } from "../components";
import { PageIntro } from "../page-ui";
import type { PageProps } from "../page-types";
import type { MonitoringEvent } from "../types";

const PAGE_SIZE = 100;

export function EventsPage({ snapshot, stack, refresh }: PageProps) {
  const [items, setItems] = useState<MonitoringEvent[]>([]);
  const [level, setLevel] = useState("");
  const [entity, setEntity] = useState("");
  const [kind, setKind] = useState("");
  const [hours, setHours] = useState(24);
  const [cursor, setCursor] = useState<string | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const entities = useMemo(() => [
    ...(snapshot.components || []).filter(item => item.stack === stack).map(item => ({ id: item.id, label: item.name })),
    ...(snapshot.links || []).filter(item => item.stack === stack).map(item => ({ id: item.id, label: item.name })),
    ...(snapshot.devices || []).filter(item => item.stack === stack).map(item => ({ id: item.id, label: item.identity })),
  ].filter((item, index, all) => all.findIndex(candidate => candidate.id === item.id) === index), [snapshot, stack]);
  const kinds = useMemo(() => Array.from(new Set(items.map(item => item.kind))).sort(), [items]);

  useEffect(() => { setCursor(null); setItems([]); }, [stack, level, entity, kind, hours]);
  useEffect(() => {
    const controller = new AbortController();
    const since = new Date(Date.now() - hours * 3600000).toISOString();
    const query = new URLSearchParams({ stack, since, limit: String(PAGE_SIZE) });
    if (level) query.set("level", level);
    if (entity) query.set("entity", entity);
    if (kind) query.set("kind", kind);
    if (cursor) query.set("cursor", cursor);
    setBusy(true);
    api<{ items: MonitoringEvent[]; next_cursor: string | null }>(`events?${query}`, { signal: controller.signal })
      .then(result => {
        setItems(current => cursor ? [...new Map([...current, ...result.items].map(item => [item.id, item])).values()] : result.items);
        setNext(result.next_cursor); setError("");
      })
      .catch(exc => { if (exc.name !== "AbortError") setError("Unable to load events"); })
      .finally(() => setBusy(false));
    return () => controller.abort();
  }, [stack, level, entity, kind, hours, cursor, refresh, reload]);

  return <div className="spark-page">
    <PageIntro title="Monitoring events" description="State transitions and allow-listed diagnostics retained for 30 days." icon={ScrollText} />
    <div className="page-actions"><Link className="secondary-button" to="/history">View metric history</Link></div>
    <div className="filter-bar events-filter">
      <label><span>Environment</span><select aria-label="Event environment" value={stack} disabled><option value="ocudu">OCUDU</option></select></label>
      <label><span>Component or device</span><select aria-label="Event component or device" value={entity} onChange={event => setEntity(event.target.value)}><option value="">All entities</option>{entities.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
      <label><span>Level</span><select aria-label="Event level" value={level} onChange={event => setLevel(event.target.value)}><option value="">All levels</option><option value="info">Info</option><option value="warning">Warning</option><option value="error">Error</option></select></label>
      <label><span>Type</span><select aria-label="Event type" value={kind} onChange={event => setKind(event.target.value)}><option value="">All types</option>{kinds.map(item => <option key={item} value={item}>{text(item)}</option>)}</select></label>
      <label><span>Time</span><select aria-label="Event time range" value={hours} onChange={event => setHours(Number(event.target.value))}><option value={1}>Last hour</option><option value={24}>Last day</option><option value={168}>Last seven days</option></select></label>
      <button className="icon-button" aria-label="Refresh events" disabled={busy} onClick={() => { setCursor(null); setItems([]); setReload(value => value + 1); }}><RefreshCw className={busy ? "spin" : ""} /></button>
    </div>
    {error && <div className="connection-banner" role="alert">{error}</div>}
    <section className="table-section">
      <header><h2>Event history</h2><span className="section-meta">{items.length}{next ? "+" : ""} results</span></header>
      <div className="data-table full-event-table">
        <div className="table-row table-head"><span>Time</span><span>Level</span><span>Type</span><span>Source</span><span>Event</span></div>
        {items.map(item => <div className="table-row" key={item.id}>
          <time>{when(item.at)}</time><span><Badge state={item.level || "info"} /></span><span className="mono">{text(item.kind)}</span>
          <span>{entities.find(candidate => candidate.id === item.entity)?.label || item.entity || "—"}</span><strong>{item.message}</strong>
        </div>)}
        {!items.length && <div className="empty-row">{busy ? "Loading events" : "No matching events"}</div>}
      </div>
      {next && <div className="pagination-bar"><button className="secondary-button" disabled={busy} onClick={() => setCursor(next)}>Load older events</button></div>}
    </section>
  </div>;
}

export function EventsPreview({ stack, refresh }: { stack: string; refresh: number }) {
  const [items, setItems] = useState<MonitoringEvent[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    const since = new Date(Date.now() - 24 * 3600000).toISOString();
    api<{items: MonitoringEvent[]}>(`events?stack=${stack}&since=${since}&limit=6`, {signal: controller.signal})
      .then(result => setItems(result.items)).catch(() => setItems([]));
    return () => controller.abort();
  }, [stack, refresh]);
  return <section className="table-section events-preview"><header><h2>Recent events</h2><Link to="/events">View history</Link></header>
    <div className="data-table event-table"><div className="table-row table-head"><span>Time</span><span>Level</span><span>Source</span><span>Event</span></div>
      {items.map(item => <div className="table-row" key={item.id}><time>{when(item.at)}</time><span><Badge state={item.level || "info"} /></span><span>{item.entity || item.kind}</span><strong>{item.message}</strong></div>)}
      {!items.length && <div className="empty-row">No monitoring events</div>}
    </div>
  </section>;
}
