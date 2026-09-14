import { Antenna, Box, Cpu, Radio, Server, Usb, UsersRound, Waypoints } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, DeviceTable, systemHealth, text, value, when } from "../components";
import type { PageProps } from "../page-types";
import type { Observation } from "../types";
import { EventsPreview } from "./EventsPage";

const topologyIcons = [Cpu, Usb, Antenna, Waypoints, Server, Box, Radio];

export function OverviewPage({ snapshot, stack, refresh }: PageProps) {
  const summary = systemHealth(snapshot, stack);
  const metric = (entity: string, name: string) => snapshot.observations.find(item => item.entity === entity && item.name === name);
  const host = snapshot.components?.find(item => item.id === "spark");
  const gnb = snapshot.components?.find(item => item.id === `${stack}:gnb`);
  const core = snapshot.components?.filter(item => item.stack === stack && item.kind === "nf") || [];
  const link = (name: string) => snapshot.links?.find(item => item.id === `${stack}:${name}` || item.name.toLowerCase() === name);
  const topology = [
    { id: "host", name: "DGX Spark", state: snapshot.health?.[stack]?.host || "unknown", reason: host?.details.health_reason, to: "/diagnostics" },
    { id: "b210", name: "B210", state: snapshot.health?.[stack]?.b210 || "unknown", reason: metric(stack, "b210_speed")?.reason || "USB presence and speed", to: "/gnb" },
    { id: "gnb", name: "OCUDU gNB", state: snapshot.health?.[stack]?.ran || "unknown", reason: gnb?.details.health_reason, to: "/gnb" },
    { id: "n2", name: "N2", state: String(link("n2")?.state || value(metric(stack, "n2_associated"))), reason: link("n2")?.details.evidence || "SCTP association", to: "/core" },
    ...["amf", "smf", "upf"].map(role => {
      const item = core.find(candidate => candidate.id === `${stack}:${role}`);
      return { id: role, name: role.toUpperCase(), state: item?.business_health || item?.health || item?.state || "unknown", reason: item?.details.health_reason || "Container health check", to: `/components/${encodeURIComponent(`${stack}:${role}`)}` };
    }),
  ];
  const devices = (snapshot.devices || []).filter(item => item.stack === stack && item.source !== "ocudu_scheduler");
  const active = devices.filter(item => item.status === "ok" && item.registration === "registered" && item.sessions.some(session => session.dnn === "oai" && session.status === "ok"));
  return <div className="spark-page overview-page">
    <section className={`status-summary state-${summary.state}`}>
      <div className="status-copy"><span className={`status-dot ${summary.state}`} /><div><h2>{summary.state === "healthy" ? "Spark is operating normally" : "Spark requires attention"}</h2><p>{summary.reason}</p></div></div>
      <time className="updated">Updated {when(snapshot.observed_at)}</time>
    </section>

    <section className="spark-topology" aria-label="Spark radio and core topology">
      {topology.map((item, index) => {
        const Icon = topologyIcons[index] || Server;
        return <Link className={`spark-topology-node state-${item.state}`} to={item.to} key={item.id}>
          <span>{item.name}</span><i><Icon /></i><strong>{text(item.state)}</strong><small>{text(String(item.reason || "Evidence unavailable"))}</small>
        </Link>;
      })}
    </section>

    <div className="spark-overview-grid">
      <section className="section-frame resource-panel"><header><h2>Host resources</h2><span className="section-meta">Live</span></header>
        <div className="resource-grid">
          <Resource label="Host CPU utilization" observation={metric("spark", "cpu_usage")} total={1} />
          <Resource label="Memory utilization" observation={metric("spark", "memory_used")} capacity={metric("spark", "memory_total")} />
          <Resource label="Disk utilization" observation={metric("spark", "disk_used")} capacity={metric("spark", "disk_total")} />
          <Resource label="Temperature" observation={metric("spark", "temperature")} total={100} />
        </div>
        <div className="traffic-summary">
          <Traffic label="Host receive" observation={metric("spark", "host_rx")} detail="Default-route host traffic" />
          <Traffic label="Host transmit" observation={metric("spark", "host_tx")} detail="Default-route host traffic" />
          <Traffic label="Cell downlink" observation={metric(`${stack}:gnb`, "dl_bps")} detail="UE MAC goodput" />
          <Traffic label="Cell uplink" observation={metric(`${stack}:gnb`, "ul_bps")} detail="UE MAC goodput" />
        </div>
      </section>
      <section className="section-frame core-summary"><header><h2>Core network</h2><Link to="/core">View all {core.length}</Link></header>
        <div className="status-list">{core.map(item => <div key={item.id}><span className={`status-dot ${item.business_health || item.health || item.state}`} /><b>{item.name}</b><span>{text(item.business_health || item.health || item.state)}</span></div>)}</div>
      </section>
    </div>

    <section className="table-section devices-preview"><header><h2>Attached devices</h2><span className="section-meta"><UsersRound />{active.length} active</span></header><DeviceTable devices={active.slice(0, 5)} /></section>
    <EventsPreview stack={stack} refresh={refresh} />
  </div>;
}

function Resource({ label, observation, capacity, total }: { label: string; observation?: Observation; capacity?: Observation; total?: number }) {
  const raw = observation?.status === "ok" && typeof observation.value === "number" ? observation.value : null;
  const max = capacity?.status === "ok" && typeof capacity.value === "number" ? capacity.value : total;
  const percentage = raw != null && max ? Math.max(0, Math.min(100, raw / max * 100)) : 0;
  return <div><span>{label}</span><strong>{value(observation)}</strong><i><em style={{width: `${percentage}%`}} /></i></div>;
}

function Traffic({ label, observation, detail }: { label: string; observation?: Observation; detail: string }) {
  return <span>{label}<strong>{value(observation)}</strong><small>{detail}</small></span>;
}
