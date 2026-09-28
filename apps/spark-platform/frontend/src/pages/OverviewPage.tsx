import { activeDataSession } from "../freshness";
import {
  proportional,
  Banner,
  Card,
  Grid,
  Heading,
  Link,
  ProgressBar,
  Stack,
  Table,
  Text,
} from "@astryxdesign/core";
import {
  Antenna,
  Box,
  Cpu,
  Radio,
  Server,
  Usb,
  UsersRound,
  Waypoints,
} from "lucide-react";
import {
  Badge,
  DeviceTable,
  systemHealth,
  text,
  value,
  when,
} from "../components";
import type { PageProps } from "../page-types";
import type { Observation } from "../types";
import { EventsPreview } from "./EventsPage";
const topologyIcons = [Cpu, Usb, Antenna, Waypoints, Server, Box, Radio];
export function OverviewPage({ snapshot, stack, refresh }: PageProps) {
  const summary = systemHealth(snapshot, stack);
  const metric = (entity: string, name: string) =>
    snapshot.observations.find(
      (item) => item.entity === entity && item.name === name,
    );
  const host = snapshot.components?.find((item) => item.id === "spark");
  const gnb = snapshot.components?.find((item) => item.id === `${stack}:gnb`);
  const core =
    snapshot.components?.filter(
      (item) => item.stack === stack && item.kind === "nf",
    ) || [];
  const link = (name: string) =>
    snapshot.links?.find(
      (item) =>
        item.id === `${stack}:${name}` || item.name.toLowerCase() === name,
    );
  const topology = [
    {
      id: "host",
      name: "DGX Spark",
      state: snapshot.health?.[stack]?.host || "unknown",
      reason: host?.details.health_reason,
      to: "/diagnostics",
    },
    {
      id: "b210",
      name: "B210",
      state: snapshot.health?.[stack]?.b210 || "unknown",
      reason: metric(stack, "b210_speed")?.reason || "USB presence and speed",
      to: "/gnb",
    },
    {
      id: "gnb",
      name: "OCUDU gNB",
      state: snapshot.health?.[stack]?.ran || "unknown",
      reason: gnb?.details.health_reason,
      to: "/gnb",
    },
    {
      id: "n2",
      name: "N2",
      state: String(link("n2")?.state || value(metric(stack, "n2_associated"))),
      reason: link("n2")?.details.evidence || "SCTP association",
      to: "/core",
    },
    ...["amf", "smf", "upf"].map((role) => {
      const item = core.find(
        (candidate) => candidate.id === `${stack}:${role}`,
      );
      return {
        id: role,
        name: role.toUpperCase(),
        state:
          item?.business_health || item?.health || item?.state || "unknown",
        reason: item?.details.health_reason || "Container health check",
        to: `/components/${encodeURIComponent(`${stack}:${role}`)}`,
      };
    }),
  ];
  const devices = (snapshot.devices || []).filter(
    (item) => item.stack === stack && item.source !== "ocudu_scheduler",
  );
  const active = devices.filter(activeDataSession);
  return (
    <Stack className="spark-page overview-page" gap={4}>
      <Banner
        status={summary.state === "healthy" ? "success" : "warning"}
        title={
          summary.state === "healthy"
            ? "Spark is operating normally"
            : "Spark requires attention"
        }
        description={summary.reason}
        endContent={
          <Text type="supporting">Updated {when(snapshot.observed_at)}</Text>
        }
      />
      <Stack gap={3}>
        <Heading level={2}>Radio and core evidence</Heading>
        <Grid
          columns={{ minWidth: 180, repeat: "fit" }}
          gap={3}
          aria-label="Spark radio and core topology"
        >
          {topology.map((item, index) => {
            const Icon = topologyIcons[index] || Server;
            return (
              <Card className="spark-topology-node" key={item.id}>
                <Stack gap={3}>
                  <Stack direction="horizontal" gap={2} align="center">
                    <Icon size={18} />
                    <Link href={item.to}>{item.name}</Link>
                  </Stack>
                  <Badge state={item.state} />
                  <Text type="supporting" color="secondary">
                    {text(String(item.reason || "Evidence unavailable"))}
                  </Text>
                </Stack>
              </Card>
            );
          })}
        </Grid>
      </Stack>

      <Grid
        className="spark-overview-grid"
        columns={{ minWidth: 320, max: 2, repeat: "fit" }}
        gap={4}
      >
        <Card className="section-frame resource-panel">
          <Stack gap={4}>
            <Stack
              gap={3}
              direction="horizontal"
              align="center"
              justify="between"
              wrap="wrap"
            >
              <Heading level={2}>Host resources</Heading>
              <span className="section-meta">Live</span>
            </Stack>
            <Grid
              className="resource-grid"
              columns={{ minWidth: 180, repeat: "fit" }}
              gap={4}
            >
              <Resource
                label="Host CPU utilization"
                observation={metric("spark", "cpu_usage")}
                total={1}
              />
              <Resource
                label="Memory utilization"
                observation={metric("spark", "memory_used")}
                capacity={metric("spark", "memory_total")}
              />
              <Resource
                label="Disk utilization"
                observation={metric("spark", "disk_used")}
                capacity={metric("spark", "disk_total")}
              />
              <Resource
                label="Temperature"
                observation={metric("spark", "temperature")}
                total={100}
              />
            </Grid>
            <Grid
              className="traffic-summary"
              columns={{ minWidth: 180, repeat: "fit" }}
              gap={4}
            >
              <Traffic
                label="Host receive"
                observation={metric("spark", "host_rx")}
                detail="Default-route host traffic"
              />
              <Traffic
                label="Host transmit"
                observation={metric("spark", "host_tx")}
                detail="Default-route host traffic"
              />
              <Traffic
                label="Cell downlink"
                observation={metric(`${stack}:gnb`, "dl_bps")}
                detail="UE MAC goodput"
              />
              <Traffic
                label="Cell uplink"
                observation={metric(`${stack}:gnb`, "ul_bps")}
                detail="UE MAC goodput"
              />
            </Grid>
          </Stack>
        </Card>
        <Card className="section-frame core-summary">
          <Stack gap={4}>
            <Stack
              gap={3}
              direction="horizontal"
              align="center"
              justify="between"
              wrap="wrap"
            >
              <Heading level={2}>Core network</Heading>
              <Link href={"/core"}>View all {core.length}</Link>
            </Stack>
            <Table
              data={core}
              idKey="id"
              columns={[
                {
                  key: "name",
                  header: "Function",
                  width: proportional(1),
                  renderCell: (item) => (
                    <Link href={`/components/${encodeURIComponent(item.id)}`}>
                      {item.name}
                    </Link>
                  ),
                },
                {
                  key: "health",
                  header: "Health",
                  width: proportional(1),
                  renderCell: (item) => (
                    <Badge
                      state={item.business_health || item.health || item.state}
                    />
                  ),
                },
              ]}
            />
          </Stack>
        </Card>
      </Grid>

      <Card className="table-section devices-preview">
        <Stack gap={4}>
          <Stack
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Heading level={2}>Attached devices</Heading>
            <span className="section-meta">
              <UsersRound />
              {active.length} active
            </span>
          </Stack>
          <DeviceTable devices={active.slice(0, 5)} />
        </Stack>
      </Card>
      <EventsPreview stack={stack} refresh={refresh} />
    </Stack>
  );
}
function Resource({
  label,
  observation,
  capacity,
  total,
}: {
  label: string;
  observation?: Observation;
  capacity?: Observation;
  total?: number;
}) {
  const raw =
    observation?.status === "ok" && typeof observation.value === "number"
      ? observation.value
      : null;
  const max =
    capacity?.status === "ok" && typeof capacity.value === "number"
      ? capacity.value
      : total;
  const percentage =
    raw != null && max ? Math.max(0, Math.min(100, (raw / max) * 100)) : 0;
  return (
    <Stack gap={4}>
      <span>{label}</span>
      <Text weight="semibold">{value(observation)}</Text>
      {raw != null && max ? (
        <ProgressBar label={label} isLabelHidden value={percentage} />
      ) : (
        <Badge state={observation?.status || "unavailable"} />
      )}
    </Stack>
  );
}
function Traffic({
  label,
  observation,
  detail,
}: {
  label: string;
  observation?: Observation;
  detail: string;
}) {
  return (
    <Stack gap={2}>
      <Text color="secondary">{label}</Text>
      <Text type="large" weight="semibold">
        {value(observation)}
      </Text>
      <Text type="supporting" color="secondary">
        {detail}
      </Text>
    </Stack>
  );
}
