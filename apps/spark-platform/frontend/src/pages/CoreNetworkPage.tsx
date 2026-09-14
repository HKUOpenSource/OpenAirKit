import { Boxes, CircuitBoard, Network, Server, Waypoints } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Trend, text, value } from "../components";
import { DetailRows, PageIntro, SummaryItem } from "../page-ui";
import type { PageProps } from "../page-types";
import type { Component } from "../types";

export function CoreNetworkPage({ snapshot, stack, refresh }: PageProps) {
  const components = snapshot.components?.filter(item => item.stack === stack && item.kind === "nf") || [];
  const [selected, setSelected] = useState("");
  const component = useMemo(() => components.find(item => item.id === selected) || components[0], [components, selected]);
  useEffect(() => { if (component && !selected) setSelected(component.id); }, [component, selected]);
  const links = snapshot.links?.filter(item => item.stack === stack) || [];
  const bridge = snapshot.components?.find(item => item.id === `${stack}:bridge`);
  const healthy = components.filter(item => (item.business_health || item.health) === "healthy").length;
  const verified = links.filter(item => item.state === "healthy" && item.details.evidence && item.details.evidence !== "independent_ip_counters").length;
  return <div className="spark-page">
    <PageIntro title="Open5GS Core Network" description="Container services, network functions, resource use, and protocol links." icon={Boxes} />
    <div className="summary-strip">
      <SummaryItem icon={Server} label="Network functions">{components.length}</SummaryItem>
      <SummaryItem icon={CircuitBoard} label="Healthy services">{healthy}</SummaryItem>
      <SummaryItem icon={Waypoints} label="Verified links">{verified} / {links.length}</SummaryItem>
    </div>
    <section className="table-section"><header><h2>Network functions</h2><span className="section-meta"><span className={`status-dot ${healthy === components.length ? "healthy" : "degraded"}`} />{healthy} healthy</span></header>
      <div className="table-scroll"><table className="selectable-table"><thead><tr><th>Network function</th><th>Runtime</th><th>Health</th><th>CPU cores used</th><th>Memory</th><th>Restarts</th><th /></tr></thead>
        <tbody>{components.map(item => <tr key={item.id} className={item.id === component?.id ? "selected-row" : ""} onClick={() => setSelected(item.id)}>
          <td><button className="row-select" onClick={() => setSelected(item.id)}>{item.name}</button></td><td><Badge state={item.state} /></td><td><Badge state={item.business_health || item.health || "unknown"} /></td>
          <td>{value(item.metrics.find(metric => metric.name === "cpu_cores"))}</td><td>{value(item.metrics.find(metric => metric.name === "memory_used"))}</td><td>{String(item.details.restarts ?? "—")}</td>
          <td><Link aria-label={`Open ${item.name} details`} to={`/components/${encodeURIComponent(item.id)}`}>›</Link></td>
        </tr>)}</tbody></table>{!components.length && <p className="empty">No network function evidence</p>}</div>
    </section>
    <section className="link-strip" aria-label="Core network interfaces">
      {links.map(item => <div key={item.id}><Network /><span><b>{item.name}</b><small>{text(String(item.details.evidence || "Evidence unavailable"))}</small></span><Badge state={item.state} /></div>)}
      {bridge && <div><Network /><span><b>CN bridge</b><small>Diagnostic interface counters</small></span><Badge state={bridge.status || "unknown"} /></div>}
    </section>
    <section className="user-plane-section"><header><div><h2>User-plane traffic</h2><p>N3, N6, and bridge values describe separate boundaries and are never added together.</p></div></header>
      <div className="user-plane-summary">
        <TrafficBoundary title="N3 GTP-U" component={findLink(links, "n3")} />
        <TrafficBoundary title="N6 payload" component={findLink(links, "n6")} />
        <TrafficBoundary title="CN bridge" component={bridge} diagnostic />
      </div>
      <div className="chart-grid user-plane-charts">
        {["n3", "n6"].flatMap(name => ["downlink_bps", "uplink_bps"].map(metric => <Trend key={name + metric} entity={`${stack}:${name}`} metric={metric} title={`${name.toUpperCase()} · ${metric === "downlink_bps" ? "Downlink" : "Uplink"}`} refresh={refresh} />))}
      </div>
    </section>
    {component && <div className="component-focus">
      <section className="section-frame detail-panel"><header><h2>{component.name} details</h2><Badge state={component.business_health || component.health || component.state} /></header>
        <DetailRows values={{runtime_state: text(component.state), health_reason: text(String(component.details.health_reason || "No health reason reported")), cpu_utilization: value(component.metrics.find(item => item.name === "cpu_utilization")), cpu_cores_used: value(component.metrics.find(item => item.name === "cpu_cores")), memory_used: value(component.metrics.find(item => item.name === "memory_used")), ...component.details}} />
      </section>
      <Trend entity={component.id} metric="cpu_utilization" title={`${component.name} CPU utilization`} refresh={refresh} />
    </div>}
  </div>;
}

function findLink(links: Component[], name: string) {
  return links.find(item => item.id === `ocudu:${name}` || item.name.toLowerCase() === name);
}

function TrafficBoundary({ title, component, diagnostic = false }: { title: string; component?: Component; diagnostic?: boolean }) {
  const first = component?.metrics.find(item => item.name === (diagnostic ? "bridge_rx" : "downlink_bps"));
  const second = component?.metrics.find(item => item.name === (diagnostic ? "bridge_tx" : "uplink_bps"));
  return <div><span>{title}{diagnostic && <small>Diagnostic</small>}</span><strong>{value(first)}</strong><em>{diagnostic ? "Receive" : "Downlink"}</em><strong>{value(second)}</strong><em>{diagnostic ? "Transmit" : "Uplink"}</em></div>;
}
