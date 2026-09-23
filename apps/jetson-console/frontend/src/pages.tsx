import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Database, Download, Globe2, Network, RadioTower, RefreshCw, Server, ShieldCheck, Smartphone, UserCheck } from "lucide-react";
import { api, download, number, Obj, bitrate, when } from "./api";
import { Badge, Empty, Fields, JobPanel, MiniChart } from "./components";

export type Context = {
  status: Obj;
  config: Obj;
  jobs: Obj[];
  refresh: () => void;
  error: (value: string) => void;
  begin: (kind: string, params?: Obj) => void;
  maintenance: () => void;
};

function PageTitle({ description, children }: { title: string; description: string; children?: React.ReactNode }) {
  return <div className="page-tools"><p>{description}</p>{children ? <div className="actions">{children}</div> : null}</div>;
}

export function Overview(context: Context) {
  const state = context.status;
  const radio = state.radio || {};
  const session = state.data_session || {};
  const network = state.network || {};
  const [events, setEvents] = useState<Obj[]>([]);
  useEffect(() => { api("history?hours=24").then(value => setEvents(value.items.slice(0, 5))).catch(reason => context.error(String(reason))); }, [context.jobs.length]);
  const layerMap = new Map((state.layers || []).map((layer: Obj) => [layer.id, layer]));
  const accessNodes = [["sim", "Modem & SIM", Smartphone], ["radio", "5G radio", RadioTower], ["registration", "5GS registration", UserCheck]] as const;
  const dataNodes = [["rndis", "UE host interface", Network], ["data_pdu", "UE data session", Database], ["upf", "UPF data path", Server], ["ext_dn", "Test network", RadioTower], ["public", "Internet access", Globe2]] as const;
  return <>
    <PageTitle title="Overview" description="Current modem, registration and data-path evidence">
      <button onClick={() => context.begin("recover")} disabled={state.maintenance || Boolean(state.active_job)}><RefreshCw size={15} />Recover</button>
    </PageTitle>
    <section className="connection-summary"><div><Badge state={state.connected ? "connected" : state.health} /><h2>{state.connected ? "5G data connection verified" : state.maintenance ? "Maintenance mode active" : "Connection not verified"}</h2><p>{state.connection_reason}</p></div>
      <div className="summary-meta"><small>Evidence captured</small><strong>{when(state.evidence_at)}</strong><small>Data-only V2 network</small></div></section>
    <section><h2>Independent checks</h2><Fields items={[
      ["5GS registration", state.registered == null ? "Unknown" : state.registered ? "Registered" : "Not registered"],
      ["Data PDU", state.data_session_active == null ? "Unknown" : state.data_session_active ? "Active" : "Inactive"],
      ["Lab policy (observation only)", state.lab_policy_match == null ? "Unknown" : state.lab_policy_match ? "Matched" : "Mismatch"],
      ["Protected management", state.management_protected == null ? "Unknown" : state.management_protected ? "Verified" : "Unverified"]]} /></section>
    <section><div className="section-heading"><div><h2>Connection topology</h2><small>Each link needs current independent evidence</small></div><Badge state={state.quality} /></div>
      <div className="topology-diagram"><small className="topology-label">Device & 5G access</small><div className="topology-row access">{accessNodes.map(([id, label, Icon]) => { const layer = layerMap.get(id) as Obj | undefined; return <article key={id}><b>{label}</b><span className={"topology-icon " + (layer?.state || "unknown")}><Icon size={17} /></span><strong>{layer?.state === "ok" ? "Verified" : layer?.state || "Unknown"}</strong><small>{layer?.reason || "No current evidence"}</small></article>; })}</div>
        <small className="topology-label data-label">Data connectivity</small><div className="topology-row data">{dataNodes.map(([id, label, Icon]) => { const layer = layerMap.get(id) as Obj | undefined; return <article key={id}><b>{label}</b><span className={"topology-icon " + (layer?.state || "unknown")}><Icon size={17} /></span><strong>{layer?.state === "ok" ? "Verified" : layer?.state || "Unknown"}</strong><small>{layer?.reason || "No current evidence"}</small></article>; })}</div></div>
      {!state.layers?.length ? <Empty>Connection evidence is unavailable</Empty> : null}</section>
    {state.active_job?.kind === "recover" || context.jobs.some(item => item.kind === "recover") ? <JobPanel job={state.active_job?.kind === "recover" ? state.active_job : context.jobs.find(item => item.kind === "recover") || null} refresh={context.refresh} error={context.error} /> : null}
    <div className="grid two"><section><div className="section-heading"><h2>Radio signal</h2><span className="plain-state">NR SA · n{radio.band || "--"}</span></div>
      <div className="metric-row">{[["RSRP", radio.rsrp_dbm, "dBm"], ["RSRQ", radio.rsrq_db, "dB"], ["SINR", radio.sinr_db, "dB"]].map(([label, value, unit]) => <div key={String(label)}><small>{label}</small><strong>{number(value)}</strong><span>{unit}</span></div>)}</div>
      <Fields items={[["RRC state", radio.state], ["Serving PLMN", radio.plmn], ["Physical cell ID", radio.pci], ["Serving SSB ARFCN", radio.ssb_arfcn]]} /></section>
      <section><div className="section-heading"><h2>Data session</h2><Badge state={session.active && session.pool_valid ? "active" : "unknown"} /></div>
        <Fields items={[["DNN / CID", session.dnn ? `${session.dnn} / ${session.cid}` : null], ["PDU type", session.pdu_type], ["PDU address", session.address], ["Expected address pool", session.pool_valid ? "Verified" : "Not verified"], ["RNDIS interface", network.data_interface], ["IPv4 egress", network.ipv4_egress]]} />
        <p className="footnote">Residual IMS, SOS and vendor contexts are shown read-only and do not affect V2 data health.</p></section></div>
    <div className="grid two"><section><div className="section-heading"><h2>Interface activity</h2><small>Current host-side RNDIS counters</small></div><div className="metric-row compact"><div><small><ArrowDown size={13} /> Receive</small><strong>{bitrate(network.rx_bps)}</strong><span>Mbps</span></div><div><small><ArrowUp size={13} /> Transmit</small><strong>{bitrate(network.tx_bps)}</strong><span>Mbps</span></div></div>
      <Fields items={[["IPv4 route", network.ipv4_egress], ["IPv6 data path", network.ipv6?.quality || "Unavailable"], ["Management tunnel", network.tailscale_interface]]} /></section>
      <section><div className="section-heading"><h2>Recent activity</h2><a href="/history">View history</a></div>{events.map(event => <div className="event" key={event.id}><Badge state={event.level} /><div><b>{event.message}</b><small>{when(event.at)}</small></div></div>)}{!events.length ? <Empty /> : null}</section></div>
  </>;
}

export function DeviceSetup(context: Context) {
  const [mode, setMode] = useState("automatic");
  const state = context.status;
  const target = context.config.network || {};
  const policy = context.config.selection || {};
  const reference = context.config.radio_reference || {};
  const radio = state.radio || {};
  const session = state.data_session || {};
  const job = state.active_job?.kind === "setup" ? state.active_job : context.jobs.find(item => item.kind === "setup") || null;
  const rows = [
    ["PLMN", radio.plmn, target.plmn], ["Band", radio.band ? `n${radio.band}` : null, policy.band ? `n${policy.band}` : null],
    ["Physical cell ID", radio.pci, policy.pci ?? "Any"], ["Carrier center ARFCN", "Not reported by UE", reference.carrier_arfcn],
    ["Serving SSB ARFCN", radio.ssb_arfcn, "Observed only"], ["Data DNN", session.dnn, target.data?.dnn],
    ["PDU type", session.pdu_type, target.data?.pdu_type], ["Data address", session.address, target.data?.ue_pool],
  ];
  return <><PageTitle title="Device Setup" description="Review and apply the verified data-only network contract"><Badge state={state.commissioned && state.management_verified ? "ready" : "blocked"} /></PageTitle>
    <div className="segmented" role="group" aria-label="Setup execution mode"><button className={mode === "automatic" ? "selected" : ""} onClick={() => setMode("automatic")}>Automatic</button><button className={mode === "manual" ? "selected" : ""} onClick={() => setMode("manual")}>Manual</button></div>
    <section><div className="section-heading"><div><h2>Configuration review</h2><small>Current modem evidence compared with the network access and observed lab policy</small></div><ShieldCheck size={19} /></div>
      <div className="table-wrap"><table><thead><tr><th>Parameter</th><th>Current evidence</th><th>Target</th></tr></thead><tbody>{rows.map(([label, current, expected]) => <tr key={String(label)}><td>{label}</td><td>{current ?? "Not observed"}</td><td>{expected ?? "--"}</td></tr>)}</tbody></table></div>
      <div className="callout"><b>{mode === "automatic" ? "Automatic plan" : "Manual plan"}</b><p>{mode === "automatic" ? "Runs all verified steps and stops at the first failed readback." : "Runs one persisted step per confirmation so the browser can be refreshed between steps."}</p></div>
      <div className="actions"><button className="primary" disabled={state.maintenance || Boolean(state.active_job)} onClick={() => context.begin("setup", { mode })}>Create setup plan</button></div></section>
    <JobPanel job={job} refresh={context.refresh} error={context.error} />
  </>;
}

export function History(context: Context) {
  const [hours, setHours] = useState(24);
  const [kind, setKind] = useState("");
  const [level, setLevel] = useState("");
  const [events, setEvents] = useState<Obj[]>([]);
  const [samples, setSamples] = useState<Obj[]>([]);
  useEffect(() => { Promise.all([api(`history?hours=${hours}&kind=${kind}&level=${level}`), api(`metrics?hours=${Math.min(hours, 168)}`)])
    .then(([history, metrics]) => { setEvents(history.items); setSamples(metrics); }).catch(reason => context.error(String(reason))); }, [hours, kind, level, context.jobs.length]);
  return <><PageTitle title="History" description="Signal, task and recovery evidence" />
    <div className="filters history-filters"><label>Time window<select value={hours} onChange={event => setHours(Number(event.target.value))}><option value="1">Last hour</option><option value="24">Last 24 hours</option><option value="168">Last 7 days</option><option value="720">Last 30 days</option></select></label><label>Event type<select value={kind} onChange={event => setKind(event.target.value)}><option value="">All events</option><option value="setup">Device setup</option><option value="recover">Recovery</option><option value="maintenance">Maintenance</option></select></label><label>Level<select value={level} onChange={event => setLevel(event.target.value)}><option value="">All levels</option><option value="info">Info</option><option value="warning">Warning</option><option value="error">Error</option></select></label></div>
    <div className="grid two"><MiniChart samples={samples} field={sample => sample.quality === "ok" ? sample.radio?.rsrp_dbm ?? null : null} label="Signal strength" unit="RSRP dBm" /><MiniChart samples={samples} field={sample => sample.quality === "ok" ? sample.radio?.sinr_db ?? null : null} label="Signal quality" unit="SINR dB" /></div>
    <section><div className="section-heading"><h2>Events</h2><Badge state={events.length ? "available" : "unknown"} /></div>{events.map(event => <div className="event detailed" key={event.id}><Badge state={event.level} /><div><b>{event.message}</b><small>{event.kind} · {when(event.at)}</small></div></div>)}{!events.length ? <Empty /> : null}</section>
  </>;
}

export function Settings(context: Context) {
  const state = context.status;
  const network = context.config.network || {};
  const policy = context.config.selection || {};
  const reference = context.config.radio_reference || {};
  const residual = state.other_contexts || [];
  return <><PageTitle title="Settings" description="Runtime, maintenance and diagnostic controls"><button onClick={() => download("diagnostics", `aoc-jetson-diagnostics-${Date.now()}.json`).catch(reason => context.error(String(reason)))}><Download size={15} />Export diagnostics</button></PageTitle>
    <section><div className="section-heading"><div><h2>Maintenance mode</h2><small>Stops background AT access and releases the modem serial port</small></div><label className="switch"><input type="checkbox" checked={Boolean(state.maintenance)} onChange={context.maintenance} /><span /></label></div>
      <div className="status-strip"><div><small>Device executor</small><Badge state={state.quality} /></div><div><small>Automatic recovery</small><Badge state={state.recovery_paused ? "paused" : "active"} /></div><div><small>Commissioning</small><Badge state={state.commissioned && state.management_verified ? "complete" : "blocked"} /></div></div></section>
    <div className="grid two"><section><h2>Data network contract</h2><Fields items={[["PLMN / TAC", `${network.plmn || "--"} / ${reference.tac ?? "--"}`], ["Slice", `SST ${network.slice?.sst ?? "--"}`], ["DNN", network.data?.dnn], ["PDU type", network.data?.pdu_type], ["UE address pool", network.data?.ue_pool], ["QoS target", network.data?.qos_5qi ? `5QI ${network.data.qos_5qi} (configured)` : null], ["External data network", context.config.diagnostics?.ext_dn]]} /></section>
      <section><h2>Radio reference</h2><Fields items={[["Band", policy.band ? `n${policy.band}` : null], ["Bandwidth", reference.channel_bandwidth_mhz ? `${reference.channel_bandwidth_mhz} MHz` : null], ["Subcarrier spacing", reference.common_scs_khz ? `${reference.common_scs_khz} kHz` : null], ["Carrier center ARFCN", reference.carrier_arfcn], ["Serving SSB policy", policy.mode], ["Physical cell ID", policy.pci ?? "Any"], ["Configuration revision", context.config.revision]]} /></section></div>
    <section><div className="section-heading"><div><h2>Residual modem contexts</h2><small>Visible for safety; this platform does not modify them</small></div></div><div className="table-wrap"><table><thead><tr><th>CID</th><th>Type</th><th>DNN</th><th>Ownership</th></tr></thead><tbody>{residual.map((item: Obj) => <tr key={item.cid}><td>{item.cid}</td><td>{item.type}</td><td>{item.dnn || "—"}</td><td>Read-only / external</td></tr>)}</tbody></table>{!residual.length ? <Empty>No residual contexts reported</Empty> : null}</div></section>
    <section><h2>Platform</h2><Fields items={[["Product", "Agentic-OCUDU Jetson V2"], ["Release", context.config.release], ["State retention", "Metrics 7 days · events and tasks 30 days"], ["IPv6 data path", state.network?.ipv6?.quality || "Unavailable"], ["Current evidence", when(state.evidence_at)]]} /></section>
  </>;
}
