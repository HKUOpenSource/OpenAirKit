import {
  Banner,
  Card,
  Grid,
  Heading,
  Link,
  Selector,
  Stack,
  Text,
  TextInput,
} from "@astryxdesign/core";
import {
  ArrowLeft,
  CircleUserRound,
  Network,
  Radio,
  Search,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import {
  Badge,
  Details,
  DeviceTable,
  Sessions,
  Trend,
  text,
  when,
} from "../components";
import { freshDevice } from "../freshness";
import type { PageProps } from "../page-types";
import { PageIntro, StatusSummary } from "../page-ui";
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
      api<{
        items: Device[];
      }>(
        `devices?stack=${stack}&scope=${scope}&query=${encodeURIComponent(query)}`,
        { signal: controller.signal },
      )
        .then((result) => {
          setItems(
            result.items.map((item) =>
              freshDevice(item, snapshot.collector_status === "ok"),
            ),
          );
          setError("");
        })
        .catch((exc) => {
          if (exc.name !== "AbortError") setError("Unable to load devices");
        });
    }, 180);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [
    stack,
    scope,
    query,
    refresh,
    snapshot.observed_at,
    snapshot.collector_status,
  ]);
  const filtered = items.filter((item) => {
    if (!state) return true;
    if (state === "active")
      return (
        item.status === "ok" &&
        item.registration === "registered" &&
        item.sessions.some(
          (session) => session.dnn === "oai" && session.status === "ok",
        )
      );
    if (state === "connected") return item.connection?.state === "connected";
    if (state === "stale") return item.status === "stale";
    return item.state === state || item.registration === state;
  });
  return (
    <Stack className="spark-page" gap={4}>
      <PageIntro
        title="Attached devices"
        description="Current and recently observed radio, registration, and PDU contexts."
        icon={UsersRound}
      />
      <Stack
        className="filter-bar devices-filter"
        gap={3}
        direction="horizontal"
        align="center"
        justify="between"
        wrap="wrap"
      >
        <TextInput
          label="Search devices"
          placeholder="Identity, RNTI, NGAP ID, DNN, or PDU address"
          value={query}
          onChange={setQuery}
          startIcon={<Search size={18} />}
        />
        <Selector
          label={"Device state"}
          value={String(state)}
          options={[
            { value: String("active"), label: "Active" },
            { value: String(""), label: "All states" },
            { value: String("connected"), label: "Connected" },
            { value: String("registered"), label: "Registered" },
            { value: String("disconnected"), label: "Disconnected" },
            { value: String("stale"), label: "Stale" },
            { value: String("unknown"), label: "Unknown" },
          ]}
          onChange={(selected) => setState(selected)}
        ></Selector>
        <Selector
          label={"Inventory"}
          value={String(scope)}
          options={[
            { value: String("subscribers"), label: "Subscriber devices" },
            { value: String("radio"), label: "Unmapped radio contexts" },
          ]}
          onChange={(selected) => {
            setScope(selected);
            setState(selected === "radio" ? "" : "active");
          }}
        ></Selector>
        <span>{filtered.length} devices</span>
      </Stack>
      {error && <Banner status="error" title={error} />}
      <Card className="table-section">
        <Stack gap={4}>
          <Stack
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Heading level={2}>Device inventory</Heading>
            <span className="section-meta">30-day recent window</span>
          </Stack>
          <DeviceTable radio={scope === "radio"} devices={filtered} />
        </Stack>
      </Card>
    </Stack>
  );
}
export function DeviceDetailPage({ snapshot, refresh }: PageProps) {
  const { id = "" } = useParams();
  const [stored, setStored] = useState<Device | null>(null);
  const [error, setError] = useState("");
  const raw =
    snapshot.devices?.find((item) => item.id === id) ||
    (stored?.id === id ? stored : null);
  const device = useMemo(
    () => (raw ? freshDevice(raw, snapshot.collector_status === "ok") : null),
    [raw, snapshot.collector_status],
  );
  useEffect(() => {
    const controller = new AbortController();
    api<Device>(`devices/${encodeURIComponent(id)}`, {
      signal: controller.signal,
    })
      .then((item) => {
        setStored(item);
        setError("");
      })
      .catch((exc) => {
        if (exc.name !== "AbortError")
          setError("Device not found or outside the retention window");
      });
    return () => controller.abort();
  }, [id, refresh]);
  if (!device)
    return (
      <Stack className="spark-page" gap={4}>
        {error ? (
          <Banner status="error" title={error} />
        ) : (
          <Stack className="page-loading" gap={4}>
            Loading device
          </Stack>
        )}
      </Stack>
    );
  const displayedState =
    device.status === "ok"
      ? device.connection?.state || device.state
      : device.status;
  return (
    <Stack className="spark-page device-detail-page" gap={4}>
      <Card className="page-intro">
        <Stack gap={4}>
          <Stack gap={4}>
            <Link className="back-link" href={"/devices"}>
              <ArrowLeft />
              Devices
            </Link>
            <Heading className="mono" level={2}>
              {device.identity}
            </Heading>
            <Text as="p">
              {text(
                device.connection?.reason || "connection_evidence_incomplete",
              )}
            </Text>
          </Stack>
          <CircleUserRound />
        </Stack>
      </Card>
      <StatusSummary
        state={displayedState}
        title={text(displayedState)}
        reason={`Last observed ${when(device.observed_at)}`}
        updated={device.observed_at}
      />
      <Grid
        className="device-detail-grid"
        columns={{ minWidth: 320, repeat: "fit" }}
        gap={4}
      >
        <Card className="section-frame detail-panel">
          <Stack gap={4}>
            <Stack
              gap={3}
              direction="horizontal"
              align="center"
              justify="between"
              wrap="wrap"
            >
              <Heading level={2}>Identifiers</Heading>
              <ShieldCheck />
            </Stack>
            <Details
              values={{
                identity: device.identity,
                source: text(device.source),
                ...device.identifiers,
                correlation: text(device.correlation || "unverified"),
              }}
            />
          </Stack>
        </Card>
        <Card className="section-frame detail-panel">
          <Stack gap={4}>
            <Stack
              gap={3}
              direction="horizontal"
              align="center"
              justify="between"
              wrap="wrap"
            >
              <Heading level={2}>Radio context</Heading>
              <Radio />
            </Stack>
            <Details
              values={{
                registration: text(device.registration),
                evidence_quality: text(device.status),
                source: text(device.source),
                ...device.connection?.layers,
              }}
            />
          </Stack>
        </Card>
        <Card className="section-frame detail-panel session-panel">
          <Stack gap={4}>
            <Stack
              gap={3}
              direction="horizontal"
              align="center"
              justify="between"
              wrap="wrap"
            >
              <Heading level={2}>PDU sessions</Heading>
              <Network />
            </Stack>
            <Sessions
              sessions={device.sessions.filter(
                (session) => session.dnn === "oai",
              )}
            />
          </Stack>
        </Card>
      </Grid>
      {device.metrics.length > 0 && (
        <Grid
          className="chart-grid"
          columns={{ minWidth: 320, repeat: "fit" }}
          gap={4}
        >
          {["dl_bps", "ul_bps", "phr", "dl_bler", "ul_bler", "cqi", "sinr"]
            .filter((name) =>
              device.metrics.some((metric) => metric.name === name),
            )
            .map((name) => (
              <Trend
                key={name}
                kind="devices"
                entity={id}
                metric={name}
                refresh={refresh}
              />
            ))}
        </Grid>
      )}
      <Stack className="device-observation-times" gap={4}>
        <Stack gap={1}>
          <Text color="secondary">First observed</Text>
          <Text weight="semibold">{when(device.first_seen)}</Text>
        </Stack>
        <Stack gap={1}>
          <Text color="secondary">Last observed</Text>
          <Text weight="semibold">{when(device.observed_at)}</Text>
        </Stack>
        <Stack gap={1}>
          <Text color="secondary">Connection evidence</Text>
          <Badge state={displayedState} />
        </Stack>
      </Stack>
    </Stack>
  );
}
