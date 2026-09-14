import { ArrowLeft, CircleUserRound, Network, Radio, Search, ShieldCheck, UsersRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { Badge, Details, DeviceTable, Sessions, Trend, text, when } from "../components";
import { freshDevice } from "../freshness";
import { PageIntro, StatusSummary } from "../page-ui";
import type { PageProps } from "../page-types";
import type { Device } from "../types";

export function DevicesPage({ snapshot, stack, refresh }: PageProps) {
  const [items, setItems] = useState<Device[]>([]);
  const [query, setQuery] = useState("");
  const [state, setState] = useState("active");
  const [scope, setScope] = useState("subscribers");
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      api<{items: Device[]}>(`devices?stack=${stack}&scope=${scope}&query=${encodeURIComponent(query)}`, {signal: controller.signal})
        .then(result => { setItems(result.items.map(item => freshDevice(item, snapshot.collector_status === "ok"))); setError(""); })
        .catch(exc => { if (exc.name !== "AbortError") setError("Unable to load devices"); });
    }, 180);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [stack, scope, query, refresh, snapshot.observed_at, snapshot.collector_status]);
  const filtered = items.filter(item => {
    if (!state) return true;
    if (state === "active") return item.status === "ok" && item.registration === "registered" && item.sessions.some(session => session.dnn === "oai" && session.status === "ok");
    if (state === "connected") return item.connection?.state === "connected";
    if (state === "stale") return item.status === "stale";
    return item.state === state || item.registration === state;
  });
  return <div className="spark-page">
    <PageIntro title="Attached devices" description="Current and recently observed radio, registration, and PDU contexts." icon={UsersRound} />
    <div className="filter-bar devices-filter">
      <label className="search-field"><Search /><input aria-label="Search devices" placeholder="Search masked identity, RNTI, NGAP ID, DNN, or PDU address" value={query} onChange={event => setQuery(event.target.value)} /></label>
      <label><span>State</span><select aria-label="Device state" value={state} onChange={event => setState(event.target.value)}><option value="active">Active</option><option value="">All states</option><option value="connected">Connected</option><option value="registered">Registered</option><option value="disconnected">Disconnected</option><option value="stale">Stale</option><option value="unknown">Unknown</option></select></label>
      <label><span>Inventory</span><select aria-label="Inventory" value={scope} onChange={event => { setScope(event.target.value); setState(event.target.value === "radio" ? "" : "active"); }}><option value="subscribers">Subscriber devices</option><option value="radio">Unmapped radio contexts</option></select></label>
      <span>{filtered.length} devices</span>
    </div>
    {error && <div className="connection-banner" role="alert">{error}</div>}
    <section className="table-section"><header><h2>Device inventory</h2><span className="section-meta">30-day recent window</span></header><DeviceTable radio={scope === "radio"} devices={filtered} /></section>
  </div>;
}

export function DeviceDetailPage({ snapshot, refresh }: PageProps) {
  const { id = "" } = useParams();
  const [stored, setStored] = useState<Device | null>(null);
  const [error, setError] = useState("");
  const raw = snapshot.devices?.find(item => item.id === id) || (stored?.id === id ? stored : null);
  const device = useMemo(() => raw ? freshDevice(raw, snapshot.collector_status === "ok") : null, [raw, snapshot.collector_status]);
  useEffect(() => {
    const controller = new AbortController();
    api<Device>(`devices/${encodeURIComponent(id)}`, {signal: controller.signal})
      .then(item => { setStored(item); setError(""); })
      .catch(exc => { if (exc.name !== "AbortError") setError("Device not found or outside the retention window"); });
    return () => controller.abort();
  }, [id, refresh]);
  if (!device) return <div className="spark-page">{error ? <div className="connection-banner">{error}</div> : <div className="page-loading">Loading device</div>}</div>;
  const displayedState = device.status === "ok" ? device.connection?.state || device.state : device.status;
  return <div className="spark-page device-detail-page">
    <section className="page-intro"><div><Link className="back-link" to="/devices"><ArrowLeft />Devices</Link><h2 className="mono">{device.identity}</h2><p>{text(device.connection?.reason || "connection_evidence_incomplete")}</p></div><CircleUserRound /></section>
    <StatusSummary state={displayedState} title={text(displayedState)} reason={`Last observed ${when(device.observed_at)}`} updated={device.observed_at} />
    <div className="device-detail-grid">
      <section className="section-frame detail-panel"><header><h2>Identifiers</h2><ShieldCheck /></header><Details values={{identity: device.identity, ...device.identifiers, correlation: text(device.correlation || "unverified")}} /></section>
      <section className="section-frame detail-panel"><header><h2>Radio context</h2><Radio /></header><Details values={{registration: text(device.registration), evidence_quality: text(device.status), source: text(device.source), ...device.connection?.layers}} /></section>
      <section className="section-frame detail-panel session-panel"><header><h2>PDU sessions</h2><Network /></header><Sessions sessions={device.sessions.filter(session => session.dnn === "oai")} /></section>
    </div>
    {device.metrics.length > 0 && <div className="chart-grid">{["dl_bps", "ul_bps", "phr", "dl_bler", "ul_bler", "cqi", "sinr"].filter(name => device.metrics.some(metric => metric.name === name)).map(name => <Trend key={name} kind="devices" entity={id} metric={name} refresh={refresh} />)}</div>}
    <div className="device-observation-times"><span>First observed<strong>{when(device.first_seen)}</strong></span><span>Last observed<strong>{when(device.observed_at)}</strong></span><span>Connection evidence<strong><Badge state={displayedState} /></strong></span></div>
  </div>;
}
