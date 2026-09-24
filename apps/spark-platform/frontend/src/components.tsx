import { Chart, ChartAxis, line } from "@astryxdesign/charts";
import {
  Badge as AstryxBadge,
  Card,
  EmptyState,
  Grid,
  Heading,
  Link,
  MetadataList,
  MetadataListItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
} from "@astryxdesign/core";
import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type {
  Device,
  MetricPoint,
  Observation,
  Session,
  Snapshot,
} from "./types";
export const CollectionAvailable = createContext(false);
export const CurrentSnapshot = createContext<Snapshot | null>(null);
export function systemHealth(s: Snapshot | null, stack: string) {
  if (!s || s.collector_status !== "ok")
    return {
      state: "unknown",
      reason: "Current collection evidence is unavailable",
    };
  const h = s.health?.[stack];
  if (!h)
    return {
      state: "unknown",
      reason: "Network health evidence is unavailable",
    };
  const labels: Record<string, string> = {
    host: "Host",
    b210: "B210",
    ran: "Radio access",
    core: "Core network",
  };
  const state =
    ["failed", "degraded", "unknown"].find((v) =>
      Object.keys(labels).some((k) => h[k] === v || (v === "unknown" && !h[k])),
    ) || (h.ran === "inactive" ? "degraded" : "healthy");
  const reasons = Object.keys(labels)
    .filter((k) => h[k] !== "healthy")
    .map((k) => `${labels[k]}: ${text(h[k] || "unknown")}`);
  return {
    state,
    reason:
      reasons.join(" · ") ||
      "Host, radio access and core network checks passed",
  };
}
const labels: Record<string, string> = {
  ok: "Available",
  stale: "Stale",
  unavailable: "Unavailable",
  unsupported: "Unsupported",
  healthy: "Healthy",
  unhealthy: "Unhealthy",
  running: "Running",
  exited: "Stopped",
  active: "Running",
  inactive: "Stopped",
  unknown: "Unknown",
  none: "Not running",
  ocudu: "OCUDU",
  succeeded: "Completed",
  failed: "Failed",
  interrupted: "Interrupted",
  registered: "Registered",
  deregistered: "Deregistered",
  disconnected: "Deregistered",
  radio_observed: "Radio observed",
  released: "Radio context released",
  reported: "Reported",
  recent_report: "Recent report",
  degraded: "Degraded",
  queued: "Queued",
  pending: "Pending",
  reachable: "Address reachable",
  address_reachable: "UE address reachable",
  unreachable: "No ICMP reply",
  unverified: "Unverified",
  amf_periodic_table: "AMF registration report",
  smf_context_summary: "SMF session report",
  ocudu_scheduler: "OCUDU scheduler",
  spark_ext_dn_icmp: "Spark ext-DN ICMP",
  registration_not_data_connectivity: "AMF registration reported",
  spark_to_ue_address_only:
    "ICMP reply from the UE address; session activation is not established by this probe",
  radio_process_failed: "gNB service failed",
  radio_inactive: "gNB service is stopped",
  radio_evidence_unavailable:
    "Runtime, USB ownership or N2 evidence is incomplete",
  radio_hardware_fault: "B210 is missing or has conflicting owners",
  n2_not_associated: "No SCTP association to the configured AMF",
  radio_usb_owner_mismatch: "The gNB PID does not exclusively own B210",
  usb_speed_below_usb3: "B210 USB speed is below 5 Gbps",
  process_usb_owner_and_n2_verified:
    "Process, B210 ownership and N2 association verified",
  recent_radio_error_events:
    "Radio error events were reported in the current sampling window",
  sctp_association: "SCTP association to the configured AMF",
  pfcp_udp_listener_not_association:
    "PFCP UDP listener observed; association unverified",
  independent_ip_counters:
    "Independent interface counters; protocol session health unverified",
  protocol_evidence_unavailable: "No current protocol evidence",
  connection_evidence_incomplete: "Insufficient current connection evidence",
  explicit_deregistration_report: "AMF explicitly reported deregistration",
  radio_context_not_subscriber_connection:
    "Radio context observed; subscriber identity unverified",
  icmp_no_reply_not_session_release:
    "No ICMP reply; PDU release not established",
  no_fresh_data_session: "No current data session report to probe",
  probe_expired_or_unavailable: "Probe expired or unavailable",
  probe_confirmation_pending: "Waiting for a second successful probe",
  ambiguous_address_owner: "Multiple sessions report this address",
  no_interface_bound_ue_probe_source:
    "Jetson interface-bound probe not available",
  no_authoritative_session_adapter:
    "Current PDU activation not independently verified",
  open5gs_adapter_pending: "Open5GS session adapter is not enabled yet",
  no_current_qos_evidence: "No current QoS evidence",
  sample_expired: "Evidence expired",
  last_smf_report_not_live_count:
    "Recent SMF reports; not an active session count",
  deployment_contract_not_ue_confirmation:
    "Configured endpoint; UE delivery not verified",
  collector_evidence_stale: "Collector evidence is stale.",
  amf_supi: "AMF SUPI evidence",
  smf_supi_only: "SMF SUPI evidence only",
  amf_smf_supi: "AMF and SMF matched by SUPI",
  ambiguous_ngap_identifiers: "Ambiguous NGAP identifiers",
  radio_only: "Uncorrelated radio context",
};
export const fieldLabel = (s: string) =>
  s.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
export const text = (s: string) =>
  labels[s] || (s.includes("_") ? fieldLabel(s) : s);
export const when = (s?: string) =>
  s
    ? new Date(s).toLocaleString("en-GB", {
        hour12: false,
        timeZone: "Asia/Hong_Kong",
      }) + " HKT"
    : "—";
export const names: Record<string, string> = {
  cpu_usage: "Host CPU",
  cpu_cores: "CPU cores used",
  cpu_capacity: "CPU capacity",
  cpu_utilization: "CPU utilization",
  cpu_host_share: "Host CPU share",
  memory_used: "Memory used",
  memory_total: "Memory capacity",
  disk_used: "Disk used",
  disk_total: "Disk capacity",
  temperature: "Maximum temperature",
  uptime: "Uptime",
  radio_pid: "gNB PID",
  host_rx: "Host receive",
  host_tx: "Host transmit",
  default_interface: "Default interface",
  log_underflows: "Underflow log events",
  log_overflows: "Overflow log events",
  log_lates: "Late log events",
  radio_process: "gNB process",
  restarts: "Restarts",
  n2_associated: "N2 association",
  dl_bps: "Radio downlink",
  ul_bps: "Radio uplink",
  dl_bler: "Downlink BLER",
  ul_bler: "Uplink BLER",
  bler: "BLER",
  cqi: "CQI",
  dl_mcs: "Downlink MCS",
  ul_mcs: "Uplink MCS",
  dl_rank: "Downlink rank",
  ul_rank: "Uplink rank",
  dl_harq_ok: "Downlink HARQ ACK",
  dl_harq_nok: "Downlink HARQ NACK",
  ul_harq_ok: "Uplink HARQ ACK",
  ul_harq_nok: "Uplink HARQ NACK",
  phr: "Power headroom",
  sinr: "PUSCH SINR",
  pusch_rsrp: "PUSCH RSRP",
  radio_contexts: "Scheduler UE count",
  rrc_connected: "RRC connections",
  rrc_mean_connections: "Mean RRC connections in window",
  rrc_peak_connections: "Sum of DU peak RRC connections",
  b210_speed: "USB speed",
  b210_serial: "USB serial",
  b210_product: "Radio device",
  b210_devices: "B210 count",
  b210_holder_pids: "USB holder PIDs",
  active_pdu_count: "Verified active PDU count",
  reported_pdu_count: "Recent PDU reports",
  historical_pdu_count: "Historical PDU reports",
  observed_5qi: "Observed 5QI",
  bridge_rx: "Bridge receive",
  bridge_tx: "Bridge transmit",
  downlink_bps: "Downlink",
  uplink_bps: "Uplink",
  registration: "Registration",
  radio: "Radio identity",
  data_pdu: "Data PDU",
  ran_ue_ngap_id: "RAN UE NGAP ID",
  amf_ue_ngap_id: "AMF UE NGAP ID",
  rnti: "RNTI",
  cu_ue_id: "CU UE ID",
  pci: "PCI",
  srate: "Sample rate (MSps)",
  tx_gain: "TX gain (dB)",
  rx_gain: "RX gain (dB)",
  nof_antennas_dl: "DL antennas",
  nof_antennas_ul: "UL antennas",
  dl_arfcn: "DL ARFCN",
  channel_bandwidth_MHz: "Channel bandwidth (MHz)",
  common_scs: "SCS (kHz)",
  source_commit: "Source commit",
};
export function value(o?: Observation) {
  if (!o || o.status !== "ok" || o.value == null)
    return o ? text(o.status) : "Pending";
  if (typeof o.value === "boolean")
    return o.value ? "Established" : "Not established";
  if (o.name === "b210_speed") return String(o.value) + " Mbps";
  if (typeof o.value === "number") {
    if (o.unit === "ratio") return (o.value * 100).toFixed(1) + "%";
    if (o.unit === "byte") return (o.value / 2 ** 30).toFixed(2) + " GiB";
    if (o.unit === "bit/s") return (o.value / 1e6).toFixed(2) + " Mbps";
    return (
      o.value.toLocaleString("en-GB", { maximumFractionDigits: 2 }) +
      (["cores", "C", "seconds", "dB"].includes(o.unit)
        ? " " + ({ C: "°C", seconds: "s" }[o.unit] || o.unit)
        : "")
    );
  }
  return Array.isArray(o.value)
    ? o.value.join(", ") || "None"
    : text(String(o.value));
}
export function Badge({ state }: { state: string }) {
  const variant = [
    "ok",
    "healthy",
    "succeeded",
    "connected",
    "registered",
    "active",
    "running",
  ].includes(state)
    ? "success"
    : ["failed", "error", "unhealthy"].includes(state)
      ? "error"
      : ["stale", "warning", "degraded", "interrupted"].includes(state)
        ? "warning"
        : "neutral";
  return (
    <AstryxBadge
      style={{ alignSelf: "flex-start" }}
      className={"badge " + state}
      label={text(state)}
      variant={variant}
    />
  );
}
export function Metrics({ items }: { items: Observation[] }) {
  return (
    <Stack className="metrics-table" gap={4}>
      {items.map((o) => (
        <Grid
          className="metric-row"
          key={o.entity + o.name}
          columns={{ minWidth: 180, repeat: "fit" }}
          gap={4}
        >
          <Stack gap={1}>
            {names[o.name] || fieldLabel(o.name)}
            <Text type="supporting" color="secondary">
              {o.entity.includes(":") ? o.entity.split(":").at(-1) : ""}
            </Text>
          </Stack>
          <Stack gap={1}>
            <Text weight="semibold">{value(o)}</Text>
            {o.reason && (
              <Text type="supporting" color="secondary">
                {text(o.reason)}
              </Text>
            )}
          </Stack>
          <Badge state={o.status} />
        </Grid>
      ))}
    </Stack>
  );
}
export function Details({ values }: { values: Record<string, unknown> }) {
  return (
    <MetadataList columns="single">
      {Object.entries(values).map(([key, item]) => (
        <MetadataListItem
          key={key}
          label={names[key] || (key.includes(" ") ? key : fieldLabel(key))}
        >
          {item == null
            ? "—"
            : typeof item === "boolean"
              ? item
                ? "Enabled"
                : "Disabled"
              : typeof item === "object"
                ? JSON.stringify(item)
                : labels[String(item)] || String(item)}
        </MetadataListItem>
      ))}
    </MetadataList>
  );
}
export function Sessions({ sessions }: { sessions: Session[] }) {
  return (
    <Stack className="table-scroll" gap={4}>
      <Table style={{ minWidth: 1000 }}>
        <TableHeader>
          <TableRow isHeaderRow>
            <TableHeaderCell>PDU ID</TableHeaderCell>
            <TableHeaderCell>DNN</TableHeaderCell>
            <TableHeaderCell>Address</TableHeaderCell>
            <TableHeaderCell>S-NSSAI</TableHeaderCell>
            <TableHeaderCell>QFI</TableHeaderCell>
            <TableHeaderCell>5QI</TableHeaderCell>
            <TableHeaderCell>N3 endpoint pair</TableHeaderCell>
            <TableHeaderCell>Report status</TableHeaderCell>
            <TableHeaderCell>Evidence time</TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sessions.map((s, i) => (
            <TableRow key={s.id + ":" + i}>
              <TableCell>{s.id}</TableCell>
              <TableCell>{s.dnn || "—"}</TableCell>
              <TableCell className="mono">{s.address || "—"}</TableCell>
              <TableCell>
                {s.sst ?? "—"} / {s.sd ?? "—"}
              </TableCell>
              <TableCell>{s.qfi ?? "Unverified"}</TableCell>
              <TableCell>{s.five_qi ?? "Unverified"}</TableCell>
              <TableCell>
                {s.n3_verified === true ? "Verified" : "Unverified"}
              </TableCell>
              <TableCell>
                <Badge state={s.state} />
                <Badge state={s.status} />
              </TableCell>
              <TableCell>{when(s.observed_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {!sessions.length && <EmptyState title="No session evidence" isCompact />}
    </Stack>
  );
}
export function DeviceTable({
  devices,
  radio = false,
}: {
  devices: Device[];
  radio?: boolean;
}) {
  return (
    <Stack className="table-scroll" gap={4}>
      <Table style={{ minWidth: radio ? 920 : 760 }}>
        <TableHeader>
          <TableRow isHeaderRow>
            <TableHeaderCell>Identity</TableHeaderCell>
            <TableHeaderCell>State</TableHeaderCell>
            {radio && (
              <>
                <TableHeaderCell>RNTI</TableHeaderCell>
                <TableHeaderCell>Power headroom</TableHeaderCell>
              </>
            )}
            {radio ? (
              <TableHeaderCell>Downlink / uplink</TableHeaderCell>
            ) : (
              <>
                <TableHeaderCell>PDU addresses</TableHeaderCell>
                <TableHeaderCell>DNNs</TableHeaderCell>
              </>
            )}
            <TableHeaderCell>Last seen</TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {devices.map((d) => (
            <TableRow key={d.id}>
              <TableCell>
                <Link
                  href={"/devices/" + encodeURIComponent(d.id)}
                  style={{ whiteSpace: "nowrap" }}
                >
                  {d.identity}
                </Link>
              </TableCell>
              <TableCell>
                <Badge
                  state={
                    d.status === "ok"
                      ? d.connection?.state || d.state
                      : d.status
                  }
                />
              </TableCell>
              {radio && (
                <>
                  <TableCell className="mono">
                    {String(d.identifiers.rnti ?? "—")}
                  </TableCell>
                  <TableCell>
                    {value(d.metrics.find((m) => m.name === "phr"))}
                  </TableCell>
                </>
              )}
              {radio ? (
                <TableCell>
                  {value(d.metrics.find((m) => m.name === "dl_bps"))} /{" "}
                  {value(d.metrics.find((m) => m.name === "ul_bps"))}
                </TableCell>
              ) : (
                <>
                  <TableCell className="session-values mono">
                    <Stack gap={1}>
                      {d.sessions
                        .filter((s) => s.dnn === "oai")
                        .map((s) => (
                          <span key={s.id} title={when(s.observed_at)}>
                            {s.address || "—"}
                          </span>
                        ))}
                    </Stack>
                  </TableCell>
                  <TableCell className="session-values">
                    <Stack gap={1}>
                      {d.sessions
                        .filter((s) => s.dnn === "oai")
                        .map((s) => (
                          <span key={s.id}>{s.dnn || "—"}</span>
                        ))}
                    </Stack>
                  </TableCell>
                </>
              )}
              <TableCell>{when(d.observed_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {!devices.length && <EmptyState title="No device evidence" isCompact />}
    </Stack>
  );
}
export function Trend({
  entity,
  metric,
  hours = 1,
  refresh = 0,
  kind = "components",
  title,
}: {
  entity: string;
  metric: string;
  hours?: number;
  refresh?: number;
  kind?: string;
  title?: string;
}) {
  const available = useContext(CollectionAvailable);
  const snapshot = useContext(CurrentSnapshot);
  const [items, setItems] = useState<MetricPoint[]>([]),
    [error, setError] = useState("");
  const requestKey = `${kind}:${entity}:${hours}`;
  const [loadedKey, setLoadedKey] = useState("");
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const since = new Date(Date.now() - hours * 3600000).toISOString();
    api<{
      items: MetricPoint[];
    }>(
      `${kind}/${encodeURIComponent(entity)}/metrics?since=${since}&bucket=${Math.max(5, Math.ceil((hours * 3600) / 360))}`,
      { signal: controller.signal },
    )
      .then((r) => {
        setItems(r.items);
        setLoadedKey(requestKey);
        setError("");
      })
      .catch((e) => {
        if (e.name !== "AbortError") {
          setItems([]);
          setError("Unable to load history");
        }
      });
    return () => controller.abort();
  }, [entity, hours, refresh, kind]);
  const first = now - hours * 3600000,
    last = now;
  const samples = (loadedKey === requestKey ? items : [])
    .map((p) => ({
      at: Date.parse(p.at),
      o: p.metrics.find((m) => m.name === metric),
    }))
    .filter(
      (s) => Number.isFinite(s.at) && s.at >= first && s.at <= last + 5000,
    )
    .sort((a, b) => a.at - b.at);
  const valid = samples.filter(
    (s) =>
      s.o?.status === "ok" &&
      typeof s.o.value === "number" &&
      Number.isFinite(s.o.value),
  );
  const latest = samples.at(-1),
    lastValid = valid.at(-1);
  const source =
    kind === "devices"
      ? snapshot?.devices
      : [...(snapshot?.components || []), ...(snapshot?.links || [])];
  const liveMetric = source
    ?.find((c) => c.id === entity)
    ?.metrics.find((m) => m.name === metric);
  // SSE supplies the current value; history remains on the slower query cadence.
  const headline = liveMetric || latest?.o;
  const sampleAge = now - Date.parse(headline?.observed_at || "");
  const current =
    available &&
    headline?.status === "ok" &&
    typeof headline.value === "number" &&
    Number.isFinite(headline.value) &&
    sampleAge >= -5000 &&
    sampleAge <= 20000;
  const quality = current
    ? "ok"
    : !headline
      ? "unavailable"
      : headline.status !== "ok"
        ? headline.status
        : "stale";
  const unit = valid.at(-1)?.o?.unit || latest?.o?.unit || "";
  const scale =
    unit === "ratio"
      ? 100
      : unit === "bit/s"
        ? 1e-6
        : unit === "byte"
          ? 1 / 2 ** 30
          : 1;
  const unitLabel =
    (
      {
        ratio: "%",
        "bit/s": "Mbps",
        byte: "GiB",
        C: "°C",
        seconds: "s",
      } as Record<string, string>
    )[unit] || unit;
  const chartData: { at: number; value: number | null }[] = [];
  let previous = 0;
  for (const sample of samples) {
    if (
      previous &&
      sample.at - previous > Math.max(20000, (hours * 3600000) / 180)
    ) {
      chartData.push({ at: previous + 1, value: null });
    }
    chartData.push({
      at: sample.at,
      value:
        sample.o?.status === "ok" &&
        typeof sample.o.value === "number" &&
        Number.isFinite(sample.o.value)
          ? sample.o.value * scale
          : null,
    });
    previous = sample.at;
  }
  return (
    <Card className="trend-section">
      <Stack gap={4}>
        <Stack
          className="section-heading"
          direction="horizontal"
          justify="between"
          align="center"
          wrap="wrap"
        >
          <Heading level={2}>
            {title || names[metric] || fieldLabel(metric)}
          </Heading>
          <Text data-testid="current-metric">
            {current ? value(headline) : text(quality)}
          </Text>
        </Stack>
        <Text className="trend-evidence" type="supporting" color="secondary">
          {current
            ? "Sample: " + when(headline!.observed_at)
            : lastValid
              ? `Last valid: ${value(lastValid.o)} · ${when(lastValid.o!.observed_at)}`
              : error || "No valid samples"}
        </Text>
        {valid.length ? (
          <Chart
            className="chart"
            title={(title || names[metric] || fieldLabel(metric)) + " history"}
            data={chartData}
            xKey="at"
            xDomain={[first, last]}
            height={220}
            series={[
              line("value", {
                label: unitLabel,
                curve: "linear",
                dots: valid.length === 1,
              }),
            ]}
            axes={
              <>
                <ChartAxis
                  position="left"
                  maxTicks={3}
                  tickFormat={(n) =>
                    Number(n).toLocaleString("en-GB", {
                      maximumFractionDigits: 2,
                    })
                  }
                />
                <ChartAxis
                  position="bottom"
                  maxTicks={3}
                  tickFormat={(n) =>
                    new Date(Number(n)).toLocaleTimeString("en-GB", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  }
                />
              </>
            }
          />
        ) : (
          <EmptyState title={error || "No valid samples"} isCompact />
        )}
        <Stack className="chart-axis" direction="horizontal" justify="between">
          <Text type="supporting">
            {new Date(first).toLocaleTimeString("en-GB", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </Text>
          <Text type="supporting">{unitLabel}</Text>
          <Text type="supporting">Now</Text>
        </Stack>
      </Stack>
    </Card>
  );
}
