import {
  Banner,
  Button,
  Card,
  Grid,
  Heading,
  Link,
  SegmentedControl,
  SegmentedControlItem,
  Selector,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
} from "@astryxdesign/core";
import {
  ArrowDown,
  ArrowUp,
  Database,
  Download,
  Globe2,
  Network,
  RadioTower,
  RefreshCw,
  Server,
  ShieldCheck,
  Smartphone,
  UserCheck,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api, bitrate, download, number, Obj, when } from "./api";
import { Badge, Empty, Fields, JobPanel, MiniChart } from "./components";
export type Context = {
  status: Obj;
  config: Obj;
  jobs: Obj[];
  refresh: () => void;
  error: (value: string) => void;
  begin: (kind: string, params?: Obj) => void;
  maintenance: () => void;
  maintenanceBusy: boolean;
};
function PageTitle({
  description,
  children,
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <Stack
      className="page-tools"
      gap={3}
      direction="horizontal"
      align="center"
      justify="between"
      wrap="wrap"
    >
      <Text as="p">{description}</Text>
      {children ? (
        <Stack
          className="actions"
          gap={3}
          direction="horizontal"
          align="center"
          justify="between"
          wrap="wrap"
        >
          {children}
        </Stack>
      ) : null}
    </Stack>
  );
}
export function Overview(context: Context) {
  const state = context.status;
  const radio = state.radio || {};
  const session = state.data_session || {};
  const network = state.network || {};
  const [events, setEvents] = useState<Obj[]>([]);
  useEffect(() => {
    let controller: AbortController | undefined;
    const load = () => {
      controller?.abort();
      controller = new AbortController();
      const signal = controller.signal;
      api("history?hours=24", undefined, signal)
        .then((value) => {
          if (!signal.aborted) setEvents(value.items.slice(0, 5));
        })
        .catch((reason) => {
          if (reason.name !== "AbortError") context.error(String(reason));
        });
    };
    load();
    const timer = window.setInterval(load, 15000);
    return () => {
      controller?.abort();
      window.clearInterval(timer);
    };
  }, [context.jobs.length]);
  const layerMap = new Map(
    (state.layers || []).map((layer: Obj) => [layer.id, layer]),
  );
  const accessNodes = [
    ["sim", "Modem & SIM", Smartphone],
    ["radio", "5G radio", RadioTower],
    ["registration", "5GS registration", UserCheck],
  ] as const;
  const dataNodes = [
    ["rndis", "UE host interface", Network],
    ["data_pdu", "UE data session", Database],
    ["upf", "UPF data path", Server],
    ["ext_dn", "Test network", RadioTower],
    ["public", "Internet access", Globe2],
  ] as const;
  return (
    <>
      <PageTitle
        title="Overview"
        description="Current modem, registration and data-path evidence"
      >
        <Button
          onClick={() => context.begin("recover")}
          label={"Recover"}
          icon={<RefreshCw size={15} />}
          isDisabled={state.maintenance || Boolean(state.active_job)}
        ></Button>
      </PageTitle>
      <Grid columns={{ minWidth: 320, max: 2, repeat: "fit" }} gap={4}>
        <Card className="connection-summary">
          <Stack gap={4}>
            <Stack gap={4}>
              <Badge state={state.connected ? "connected" : state.health} />
              <Heading level={2}>
                {state.connected
                  ? "5G data connection verified"
                  : state.maintenance
                    ? "Maintenance mode active"
                    : "Connection not verified"}
              </Heading>
              <Text as="p">{state.connection_reason}</Text>
            </Stack>
            <Stack className="summary-meta" gap={1}>
              <Text type="supporting" color="secondary">
                Evidence captured
              </Text>
              <Text weight="semibold">{when(state.evidence_at)}</Text>
              <Text type="supporting" color="secondary">
                Data-only V2 network
              </Text>
            </Stack>
          </Stack>
        </Card>
        <Card>
          <Stack gap={4}>
            <Heading level={2}>Independent checks</Heading>
            <Fields
              items={[
                [
                  "5GS registration",
                  state.registered == null
                    ? "Unknown"
                    : state.registered
                      ? "Registered"
                      : "Not registered",
                ],
                [
                  "Data PDU",
                  state.data_session_active == null
                    ? "Unknown"
                    : state.data_session_active
                      ? "Active"
                      : "Inactive",
                ],
                [
                  "Lab policy (observation only)",
                  state.lab_policy_match == null
                    ? "Unknown"
                    : state.lab_policy_match
                      ? "Matched"
                      : "Mismatch",
                ],
                [
                  "Protected management",
                  state.management_protected == null
                    ? "Unknown"
                    : state.management_protected
                      ? "Verified"
                      : "Unverified",
                ],
              ]}
            />
          </Stack>
        </Card>
      </Grid>
      <Card>
        <Stack gap={4}>
          <Stack
            className="section-heading"
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Stack gap={4}>
              <Heading level={2}>Connection topology</Heading>
              <Text type="supporting" color="secondary">
                Each link needs current independent evidence
              </Text>
            </Stack>
            <Badge state={state.quality} />
          </Stack>
          {[
            { title: "Device & 5G access", nodes: accessNodes },
            { title: "Data connectivity", nodes: dataNodes },
          ].map((group) => (
            <Stack key={group.title} gap={3}>
              <Text weight="semibold">{group.title}</Text>
              <Grid columns={{ minWidth: 180, repeat: "fit" }} gap={3}>
                {group.nodes.map(([id, label, Icon]) => {
                  const layer = layerMap.get(id) as Obj | undefined;
                  return (
                    <Card key={id} variant="muted">
                      <Stack gap={3}>
                        <Stack direction="horizontal" gap={2} align="center">
                          <Icon size={18} />
                          <Text weight="semibold">{label}</Text>
                        </Stack>
                        <Badge state={layer?.state || "unknown"} />
                        <Text type="supporting" color="secondary">
                          {layer?.reason || "No current evidence"}
                        </Text>
                      </Stack>
                    </Card>
                  );
                })}
              </Grid>
            </Stack>
          ))}
          {!state.layers?.length ? (
            <Empty>Connection evidence is unavailable</Empty>
          ) : null}
        </Stack>
      </Card>
      {state.active_job?.kind === "recover" ||
      context.jobs.some((item) => item.kind === "recover") ? (
        <JobPanel
          job={
            state.active_job?.kind === "recover"
              ? state.active_job
              : context.jobs.find((item) => item.kind === "recover") || null
          }
          refresh={context.refresh}
          error={context.error}
        />
      ) : null}
      <Grid
        className="grid two"
        columns={{ minWidth: 320, max: 2, repeat: "fit" }}
        gap={4}
      >
        <Card>
          <Stack gap={4}>
            <Stack
              className="section-heading"
              gap={3}
              direction="horizontal"
              align="center"
              justify="between"
              wrap="wrap"
            >
              <Heading level={2}>Radio signal</Heading>
              <span className="plain-state">NR SA · n{radio.band || "--"}</span>
            </Stack>
            <Grid
              className="metric-row"
              columns={{ minWidth: 180, repeat: "fit" }}
              gap={4}
            >
              {[
                ["RSRP", radio.rsrp_dbm, "dBm"],
                ["RSRQ", radio.rsrq_db, "dB"],
                ["SINR", radio.sinr_db, "dB"],
              ].map(([label, value, unit]) => (
                <Stack key={String(label)} gap={4}>
                  <Text type="supporting" color="secondary">
                    {label}
                  </Text>
                  <Text weight="semibold">{number(value)}</Text>
                  <span>{unit}</span>
                </Stack>
              ))}
            </Grid>
            <Fields
              items={[
                ["RRC state", radio.state],
                ["Serving PLMN", radio.plmn],
                ["Physical cell ID", radio.pci],
                ["Serving SSB ARFCN", radio.ssb_arfcn],
              ]}
            />
          </Stack>
        </Card>
        <Card>
          <Stack gap={4}>
            <Stack
              className="section-heading"
              gap={3}
              direction="horizontal"
              align="center"
              justify="between"
              wrap="wrap"
            >
              <Heading level={2}>Data session</Heading>
              <Badge
                state={
                  session.active && session.pool_valid ? "active" : "unknown"
                }
              />
            </Stack>
            <Fields
              items={[
                [
                  "DNN / CID",
                  session.dnn ? `${session.dnn} / ${session.cid}` : null,
                ],
                ["PDU type", session.pdu_type],
                ["PDU address", session.address],
                [
                  "Expected address pool",
                  session.pool_valid ? "Verified" : "Not verified",
                ],
                ["RNDIS interface", network.data_interface],
                ["IPv4 egress", network.ipv4_egress],
              ]}
            />
            <Text className="footnote" as="p">
              Residual IMS, SOS and vendor contexts are shown read-only and do
              not affect V2 data health.
            </Text>
          </Stack>
        </Card>
      </Grid>
      <Grid
        className="grid two"
        columns={{ minWidth: 320, max: 2, repeat: "fit" }}
        gap={4}
      >
        <Card>
          <Stack gap={4}>
            <Stack
              className="section-heading"
              gap={3}
              direction="horizontal"
              align="center"
              justify="between"
              wrap="wrap"
            >
              <Heading level={2}>Interface activity</Heading>
              <Text type="supporting" color="secondary">
                Current host-side RNDIS counters
              </Text>
            </Stack>
            <Grid
              className="metric-row compact"
              columns={{ minWidth: 180, repeat: "fit" }}
              gap={4}
            >
              <Stack gap={4}>
                <Text type="supporting" color="secondary">
                  <ArrowDown size={13} /> Receive
                </Text>
                <Text weight="semibold">{bitrate(network.rx_bps)}</Text>
                <span>Mbps</span>
              </Stack>
              <Stack gap={4}>
                <Text type="supporting" color="secondary">
                  <ArrowUp size={13} /> Transmit
                </Text>
                <Text weight="semibold">{bitrate(network.tx_bps)}</Text>
                <span>Mbps</span>
              </Stack>
            </Grid>
            <Fields
              items={[
                ["IPv4 route", network.ipv4_egress],
                ["IPv6 data path", network.ipv6?.quality || "Unavailable"],
                ["Management tunnel", network.tailscale_interface],
              ]}
            />
          </Stack>
        </Card>
        <Card>
          <Stack gap={4}>
            <Stack
              className="section-heading"
              gap={3}
              direction="horizontal"
              align="center"
              justify="between"
              wrap="wrap"
            >
              <Heading level={2}>Recent activity</Heading>
              <Link href="/history">View history</Link>
            </Stack>
            {events.map((event) => (
              <Stack
                className="event"
                key={event.id}
                gap={3}
                direction="horizontal"
                align="center"
                justify="between"
                wrap="wrap"
              >
                <Badge state={event.level} />
                <Stack gap={4}>
                  <Text weight="semibold">{event.message}</Text>
                  <Text type="supporting" color="secondary">
                    {when(event.at)}
                  </Text>
                </Stack>
              </Stack>
            ))}
            {!events.length ? <Empty /> : null}
          </Stack>
        </Card>
      </Grid>
    </>
  );
}
export function DeviceSetup(context: Context) {
  const [mode, setMode] = useState("automatic");
  const state = context.status;
  const target = context.config.network || {};
  const policy = context.config.selection || {};
  const reference = context.config.radio_reference || {};
  const radio = state.radio || {};
  const session = state.data_session || {};
  const job =
    state.active_job?.kind === "setup"
      ? state.active_job
      : context.jobs.find((item) => item.kind === "setup") || null;
  const compare = (current: unknown, expected: unknown) =>
    state.quality !== "ok" || current == null || expected == null
      ? "Unknown"
      : String(current).toLowerCase() === String(expected).toLowerCase()
        ? "Matched"
        : "Different";
  const rows = [
    ["PLMN", radio.plmn, target.plmn, compare(radio.plmn, target.plmn)],
    [
      "Band (observed policy)",
      radio.band ? `n${radio.band}` : null,
      policy.band ? `n${policy.band}` : null,
      compare(radio.band, policy.band),
    ],
    [
      "Physical cell ID (observed policy)",
      radio.pci,
      policy.pci ?? "Any",
      policy.pci == null ? "Observation only" : compare(radio.pci, policy.pci),
    ],
    [
      "Carrier center ARFCN",
      "Not reported by UE",
      reference.carrier_arfcn,
      "Observation only",
    ],
    [
      "Serving SSB ARFCN",
      radio.ssb_arfcn,
      "No programmed target",
      "Observation only",
    ],
    [
      "Data DNN",
      session.dnn,
      target.data?.dnn,
      compare(session.dnn, target.data?.dnn),
    ],
    [
      "PDU type",
      session.pdu_type,
      target.data?.pdu_type,
      compare(session.pdu_type, target.data?.pdu_type),
    ],
    [
      "Data address / pool",
      session.address,
      target.data?.ue_pool,
      state.quality !== "ok" || !session.address || session.pool_valid == null
        ? "Unknown"
        : session.pool_valid
          ? "Matched"
          : "Different",
    ],
  ];
  const blockers = [
    !context.config.revision && "Configuration revision is unavailable.",
    !state.commissioned && "Device commissioning is incomplete.",
    !state.management_verified && "Management-route verification is required.",
    state.maintenance && "Exit maintenance mode before creating a plan.",
    state.active_job && "Finish or cancel the current task first.",
  ].filter(Boolean);
  return (
    <>
      <PageTitle
        title="Device Setup"
        description="Review and apply the verified data-only network contract"
      >
        <Badge
          state={
            state.commissioned && state.management_verified
              ? "ready"
              : "blocked"
          }
        />
      </PageTitle>
      <SegmentedControl
        label="Setup execution mode"
        value={mode}
        onChange={setMode}
      >
        <SegmentedControlItem value="automatic" label="Automatic" />
        <SegmentedControlItem value="manual" label="Manual" />
      </SegmentedControl>
      <Card>
        <Stack gap={4}>
          <Stack
            className="section-heading"
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Stack gap={4}>
              <Heading level={2}>Configuration review</Heading>
              <Text type="supporting" color="secondary">
                Current modem evidence compared with the network access and
                observed lab policy
              </Text>
            </Stack>
            <ShieldCheck size={19} />
          </Stack>
          <Stack className="table-wrap setup-desktop" gap={4}>
            <Table style={{ minWidth: 600 }}>
              <TableHeader>
                <TableRow isHeaderRow>
                  <TableHeaderCell>Parameter</TableHeaderCell>
                  <TableHeaderCell>Current evidence</TableHeaderCell>
                  <TableHeaderCell>Target</TableHeaderCell>
                  <TableHeaderCell>Assessment</TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(([label, current, expected, assessment]) => (
                  <TableRow key={String(label)}>
                    <TableCell>{label}</TableCell>
                    <TableCell>{current ?? "Not observed"}</TableCell>
                    <TableCell>{expected ?? "--"}</TableCell>
                    <TableCell>{assessment}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Stack>
          <Stack className="setup-mobile" gap={3}>
            {rows.map(([label, current, expected, assessment]) => (
              <Card key={String(label)} variant="muted">
                <Stack gap={2}>
                  <Heading level={3}>{label}</Heading>
                  <Fields
                    items={[
                      ["Current evidence", current ?? "Not observed"],
                      ["Target", expected ?? "Not specified"],
                      ["Assessment", assessment],
                    ]}
                  />
                </Stack>
              </Card>
            ))}
          </Stack>
          <Banner
            status={blockers.length ? "warning" : "info"}
            title={blockers.length ? "Setup prerequisites" : "Planned actions"}
            description={
              blockers.length
                ? blockers.join(" ")
                : "Save a baseline and protect management access; reconnect only if needed, restore the data PDU, verify the path, then prefer the 5G route. Radio policy is checked without programming a modem lock. Creating a plan does not execute it."
            }
          />
          <Text type="supporting">
            {rows.filter((row) => row[3] === "Different").length} differences ·{" "}
            {rows.filter((row) => row[3] === "Unknown").length} unknown. Address
            matching checks membership in the configured pool.
          </Text>
          <Stack className="callout" gap={4}>
            <Text weight="semibold">
              {mode === "automatic" ? "Automatic plan" : "Manual plan"}
            </Text>
            <Text as="p">
              {mode === "automatic"
                ? "Runs all verified steps and stops at the first failed readback."
                : "Runs one persisted step per confirmation so the browser can be refreshed between steps."}
            </Text>
          </Stack>
          <Stack
            className="actions"
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Button
              onClick={() => context.begin("setup", { mode })}
              label={"Create setup plan"}
              isDisabled={blockers.length > 0}
              variant="primary"
            ></Button>
          </Stack>
        </Stack>
      </Card>
      <JobPanel job={job} refresh={context.refresh} error={context.error} />
    </>
  );
}
export function History(context: Context) {
  const [{ hours, kind, level, before }, setFilters] = useState({
    hours: 24,
    kind: "",
    level: "",
    before: null as number | null,
  });
  const [events, setEvents] = useState<Obj[]>([]);
  const [samples, setSamples] = useState<Obj[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [metricError, setMetricError] = useState("");
  useEffect(() => {
    const timer = window.setInterval(
      () => setReload((value) => value + 1),
      15000,
    );
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    setEvents([]);
    setNext(null);
  }, [hours, kind, level]);
  useEffect(() => setSamples([]), [hours]);
  // Keep the selected older page stable; refresh explicitly returns to the newest page.
  const liveRefresh = before === null ? reload : 0;
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);

    api(
      `history?hours=${hours}&kind=${kind}&level=${level}${before === null ? "" : `&before=${before}`}`,
      undefined,
      controller.signal,
    )
      .then((history) => {
        if (controller.signal.aborted) return;
        setEvents((previous) =>
          before === null
            ? history.items
            : [
                ...new Map(
                  [...previous, ...history.items].map((item: Obj) => [
                    item.id,
                    item,
                  ]),
                ).values(),
              ],
        );
        setNext(history.next_cursor);
        setHistoryError("");
      })
      .catch((reason) => {
        if (reason.name !== "AbortError") setHistoryError(String(reason));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [hours, kind, level, before, liveRefresh]);
  useEffect(() => {
    const controller = new AbortController();
    api(`metrics?hours=${Math.min(hours, 168)}`, undefined, controller.signal)
      .then((metrics) => {
        if (!controller.signal.aborted) {
          setSamples(metrics);
          setMetricError("");
        }
      })
      .catch((reason) => {
        if (reason.name !== "AbortError") setMetricError(String(reason));
      });
    return () => controller.abort();
  }, [hours, reload]);
  return (
    <>
      <PageTitle
        title="History"
        description="Signal, task and recovery evidence"
      />
      <Stack
        className="filters history-filters"
        gap={3}
        direction="horizontal"
        align="center"
        justify="between"
        wrap="wrap"
      >
        <Selector
          label={"Time window"}
          value={String(hours)}
          options={[
            { value: String("1"), label: "Last hour" },
            { value: String("24"), label: "Last 24 hours" },
            { value: String("168"), label: "Last 7 days" },
            { value: String("720"), label: "Last 30 days" },
          ]}
          onChange={(selected) =>
            setFilters({ hours: Number(selected), kind, level, before: null })
          }
        ></Selector>
        <Selector
          label={"Event type"}
          value={String(kind)}
          options={[
            { value: String(""), label: "All events" },
            { value: String("setup"), label: "Device setup" },
            { value: String("recover"), label: "Recovery" },
            { value: String("maintenance"), label: "Maintenance" },
          ]}
          onChange={(selected) =>
            setFilters({ hours, kind: selected, level, before: null })
          }
        ></Selector>
        <Selector
          label={"Level"}
          value={String(level)}
          options={[
            { value: String(""), label: "All levels" },
            { value: String("info"), label: "Info" },
            { value: String("warning"), label: "Warning" },
            { value: String("error"), label: "Error" },
          ]}
          onChange={(selected) =>
            setFilters({ hours, kind, level: selected, before: null })
          }
        ></Selector>
      </Stack>
      <Button
        label="Refresh history"
        icon={<RefreshCw size={15} />}
        isLoading={loading}
        onClick={() => {
          setFilters({ hours, kind, level, before: null });
          setReload((value) => value + 1);
        }}
      />
      <Text type="supporting">
        Events: last{" "}
        {hours === 720
          ? "30 days"
          : hours === 168
            ? "7 days"
            : `${hours} hours`}
        . Metrics: last{" "}
        {hours >= 168 ? "7 days (retention limit)" : `${hours} hours`}.
        {before !== null
          ? " Older events loaded; refresh to return to the latest events."
          : " Updates every 15 seconds."}
      </Text>
      {historyError && <Banner status="error" title={historyError} />}
      {metricError && <Banner status="error" title={metricError} />}
      <Grid
        className="grid two"
        columns={{ minWidth: 320, max: 2, repeat: "fit" }}
        gap={4}
      >
        <MiniChart
          samples={samples}
          hours={Math.min(hours, 168)}
          field={(sample) =>
            sample.quality === "ok" ? (sample.radio?.rsrp_dbm ?? null) : null
          }
          label="Signal strength"
          unit="RSRP dBm"
        />
        <MiniChart
          samples={samples}
          hours={Math.min(hours, 168)}
          field={(sample) =>
            sample.quality === "ok" ? (sample.radio?.sinr_db ?? null) : null
          }
          label="Signal quality"
          unit="SINR dB"
        />
      </Grid>
      <Card>
        <Stack gap={4}>
          <Stack
            className="section-heading"
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Heading level={2}>Events</Heading>
            <Badge state={events.length ? "available" : "unknown"} />
          </Stack>
          {events.map((event) => (
            <Stack
              className="event detailed"
              key={event.id}
              gap={3}
              direction="horizontal"
              align="center"
              justify="between"
              wrap="wrap"
            >
              <Badge state={event.level} />
              <Stack gap={4}>
                <Text weight="semibold">{event.message}</Text>
                <Text type="supporting" color="secondary">
                  {event.kind} · {when(event.at)}
                </Text>
              </Stack>
            </Stack>
          ))}
          {!events.length ? (
            <Empty>{loading ? "Loading events" : "No matching events"}</Empty>
          ) : null}
          {next !== null && (
            <Button
              label="Load older events"
              isLoading={loading}
              onClick={() => setFilters({ hours, kind, level, before: next })}
            />
          )}
        </Stack>
      </Card>
    </>
  );
}
export function Settings(context: Context) {
  const state = context.status;
  const network = context.config.network || {};
  const policy = context.config.selection || {};
  const reference = context.config.radio_reference || {};
  const residual = state.other_contexts || [];
  return (
    <>
      <PageTitle
        title="Settings"
        description="Runtime, maintenance and diagnostic controls"
      >
        <Button
          onClick={() =>
            download(
              "diagnostics",
              `aoc-jetson-diagnostics-${Date.now()}.json`,
            ).catch((reason) => context.error(String(reason)))
          }
          label={"Export diagnostics"}
          icon={<Download size={15} />}
        ></Button>
      </PageTitle>
      <Card>
        <Stack gap={4}>
          <Stack
            className="section-heading"
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Stack gap={4}>
              <Heading level={2}>Maintenance mode</Heading>
              <Text type="supporting" color="secondary">
                Stops background AT access and releases the modem serial port
              </Text>
            </Stack>
            <Switch
              label="Maintenance mode"
              isLabelHidden
              value={Boolean(state.maintenance)}
              onChange={context.maintenance}
              isDisabled={context.maintenanceBusy}
            />
          </Stack>
          <Grid
            className="status-strip"
            columns={{ minWidth: 320, repeat: "fit" }}
            gap={4}
          >
            <Stack gap={4}>
              <Text type="supporting" color="secondary">
                Device executor
              </Text>
              <Badge state={state.quality} />
            </Stack>
            <Stack gap={4}>
              <Text type="supporting" color="secondary">
                Automatic recovery
              </Text>
              <Badge state={state.recovery_paused ? "paused" : "active"} />
            </Stack>
            <Stack gap={4}>
              <Text type="supporting" color="secondary">
                Commissioning
              </Text>
              <Badge
                state={
                  state.commissioned && state.management_verified
                    ? "complete"
                    : "blocked"
                }
              />
            </Stack>
          </Grid>
        </Stack>
      </Card>
      <Grid
        className="grid two"
        columns={{ minWidth: 320, max: 2, repeat: "fit" }}
        gap={4}
      >
        <Card>
          <Stack gap={4}>
            <Heading level={2}>Data network contract</Heading>
            <Fields
              items={[
                [
                  "PLMN / TAC",
                  `${network.plmn || "--"} / ${reference.tac ?? "--"}`,
                ],
                ["Slice", `SST ${network.slice?.sst ?? "--"}`],
                ["DNN", network.data?.dnn],
                ["PDU type", network.data?.pdu_type],
                ["UE address pool", network.data?.ue_pool],
                [
                  "QoS target",
                  network.data?.qos_5qi
                    ? `5QI ${network.data.qos_5qi} (configured)`
                    : null,
                ],
                ["External data network", context.config.diagnostics?.ext_dn],
              ]}
            />
          </Stack>
        </Card>
        <Card>
          <Stack gap={4}>
            <Heading level={2}>Radio reference</Heading>
            <Fields
              items={[
                ["Band", policy.band ? `n${policy.band}` : null],
                [
                  "Bandwidth",
                  reference.channel_bandwidth_mhz
                    ? `${reference.channel_bandwidth_mhz} MHz`
                    : null,
                ],
                [
                  "Subcarrier spacing",
                  reference.common_scs_khz
                    ? `${reference.common_scs_khz} kHz`
                    : null,
                ],
                ["Carrier center ARFCN", reference.carrier_arfcn],
                ["Serving SSB policy", policy.mode],
                ["Physical cell ID", policy.pci ?? "Any"],
                ["Configuration revision", context.config.revision],
              ]}
            />
          </Stack>
        </Card>
      </Grid>
      <Card>
        <Stack gap={4}>
          <Stack
            className="section-heading"
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Stack gap={4}>
              <Heading level={2}>Residual modem contexts</Heading>
              <Text type="supporting" color="secondary">
                Visible for safety; this platform does not modify them
              </Text>
            </Stack>
          </Stack>
          <Stack className="table-wrap" gap={4}>
            <Table style={{ minWidth: 600 }}>
              <TableHeader>
                <TableRow isHeaderRow>
                  <TableHeaderCell>CID</TableHeaderCell>
                  <TableHeaderCell>Type</TableHeaderCell>
                  <TableHeaderCell>DNN</TableHeaderCell>
                  <TableHeaderCell>Ownership</TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {residual.map((item: Obj) => (
                  <TableRow key={item.cid}>
                    <TableCell>{item.cid}</TableCell>
                    <TableCell>{item.type}</TableCell>
                    <TableCell>{item.dnn || "—"}</TableCell>
                    <TableCell>Read-only / external</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {!residual.length ? (
              <Empty>No residual contexts reported</Empty>
            ) : null}
          </Stack>
        </Stack>
      </Card>
      <Card>
        <Stack gap={4}>
          <Heading level={2}>Platform</Heading>
          <Fields
            items={[
              ["Product", "Agentic-OCUDU Jetson V2"],
              ["Release", context.config.release],
              ["State retention", "Metrics 7 days · events and tasks 30 days"],
              ["IPv6 data path", state.network?.ipv6?.quality || "Unavailable"],
              ["Current evidence", when(state.evidence_at)],
            ]}
          />
        </Stack>
      </Card>
    </>
  );
}
