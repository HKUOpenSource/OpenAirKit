import {
  proportional,
  AlertDialog,
  Banner,
  Button,
  Card,
  Collapsible,
  EmptyState,
  Grid,
  Heading,
  Link,
  Selector,
  Stack,
  Table,
  Text,
} from "@astryxdesign/core";
import {
  Activity,
  ArrowLeft,
  Download,
  Play,
  RotateCcw,
  Settings,
  Square,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import {
  Badge,
  Details,
  Metrics,
  Trend,
  names,
  text,
  when,
} from "../components";
import type { PageProps } from "../page-types";
import { PageIntro } from "../page-ui";
import type { Component, ControlTask, Snapshot } from "../types";
export function ComponentDetailPage({ snapshot, refresh }: PageProps) {
  const { id = "" } = useParams();
  const [stored, setStored] = useState<Component | null>(null);
  const [error, setError] = useState("");
  const component =
    [...(snapshot.components || []), ...(snapshot.links || [])].find(
      (item) => item.id === id,
    ) || (stored?.id === id ? stored : null);
  useEffect(() => {
    const controller = new AbortController();
    api<Component>(`components/${encodeURIComponent(id)}`, {
      signal: controller.signal,
    })
      .then((item) => {
        setStored(item);
        setError("");
      })
      .catch((exc) => {
        if (exc.name !== "AbortError")
          setError("Component not found or outside the retention window");
      });
    return () => controller.abort();
  }, [id, refresh]);
  return (
    <Stack className="spark-page" gap={4}>
      <Link className="back-link" href={"/core"}>
        <ArrowLeft />
        Core Network
      </Link>
      {error && <Banner status="error" title={error} />}
      {component && (
        <>
          <Card className="page-intro">
            <Stack gap={4}>
              <Stack gap={4}>
                <Heading level={2}>{component.name}</Heading>
                <Text as="p">
                  Runtime, business health, evidence, and retained metrics.
                </Text>
              </Stack>
              <Activity />
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
                <Heading level={2}>Component details</Heading>
                <Badge
                  state={
                    component.status && component.status !== "ok"
                      ? component.status
                      : component.business_health ||
                        component.health ||
                        component.state
                  }
                />
              </Stack>
              <Details
                values={{
                  kind: text(component.kind),
                  runtime_state: text(component.state),
                  evidence_time: when(component.observed_at),
                  ...component.details,
                }}
              />
            </Stack>
          </Card>
          <Card className="section-frame metric-panel">
            <Stack gap={4}>
              <Stack
                gap={3}
                direction="horizontal"
                align="center"
                justify="between"
                wrap="wrap"
              >
                <Heading level={2}>Current metrics</Heading>
              </Stack>
              <Metrics items={component.metrics} />
            </Stack>
          </Card>
          <Grid
            className="chart-grid"
            columns={{ minWidth: 320, repeat: "fit" }}
            gap={4}
          >
            {component.metrics
              .filter(
                (metric) =>
                  typeof metric.value === "number" &&
                  Number.isFinite(metric.value),
              )
              .slice(0, 8)
              .map((metric) => (
                <Trend
                  key={metric.name}
                  entity={id}
                  metric={metric.name}
                  refresh={refresh}
                />
              ))}
          </Grid>
        </>
      )}
    </Stack>
  );
}
export function HistoryPage({ stack, refresh }: PageProps) {
  type HistoryEntity = {
    id: string;
    name: string;
    apiKind: string;
    metrics: { name: string; unit: string }[];
  };
  const [options, setOptions] = useState<HistoryEntity[]>([]);
  const [catalogError, setCatalogError] = useState("");
  const [after, setAfter] = useState("");
  const [next, setNext] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    api<{ items: HistoryEntity[]; next_cursor: string | null }>(
      `history/catalog?stack=${stack}&after=${encodeURIComponent(after)}`,
      { signal: controller.signal },
    )
      .then((result) => {
        if (controller.signal.aborted) return;
        setOptions((previous) =>
          after
            ? [
                ...new Map(
                  [...previous, ...result.items].map((item) => [item.id, item]),
                ).values(),
              ]
            : result.items,
        );
        setNext(result.next_cursor);
        setCatalogError("");
      })
      .catch((exc) => {
        if (exc.name !== "AbortError")
          setCatalogError("Unable to load retained history. Refresh to retry.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [stack, after, refresh]);
  const [entity, setEntity] = useState("spark");
  const [hours, setHours] = useState(1);
  const [metric, setMetric] = useState("cpu_usage");
  const current = options.find((item) => item.id === entity) || options[0];
  const available = [
    ...new Set((current?.metrics || []).map((item) => item.name)),
  ];
  const selectedMetric = available.includes(metric)
    ? metric
    : available[0] || "";
  return (
    <Stack className="spark-page" gap={4}>
      <PageIntro
        title="Metric history"
        description="Retained component and device observations, aggregated for the selected time window."
        icon={Activity}
      />
      <Stack
        className="page-actions"
        gap={3}
        direction="horizontal"
        align="center"
        justify="between"
        wrap="wrap"
      >
        <Link className="secondary-button" href={"/events"}>
          Back to events
        </Link>
      </Stack>
      <Stack
        className="filter-bar"
        gap={3}
        direction="horizontal"
        align="center"
        justify="between"
        wrap="wrap"
      >
        <Selector
          label={"History component"}
          value={String(current?.id || "")}
          options={[
            ...options.map((item) => ({
              value: String(item.id),
              label: item.name,
            })),
          ]}
          onChange={(selected) => setEntity(selected)}
        ></Selector>
        <Selector
          label={"History metric"}
          value={String(selectedMetric)}
          options={[
            ...(!available.length
              ? [{ value: String(""), label: "No numeric metrics" }]
              : []),
            ...available.map((item) => ({
              value: String(item),
              label: names[item] || text(item),
            })),
          ]}
          onChange={(selected) => setMetric(selected)}
          isDisabled={!available.length}
        ></Selector>
        <Selector
          label={"Metric time range"}
          value={String(hours)}
          options={[
            { value: String(1), label: "One hour" },
            { value: String(24), label: "One day" },
            { value: String(168), label: "Seven days" },
          ]}
          onChange={(selected) => setHours(Number(selected))}
        ></Selector>
      </Stack>
      {catalogError && <Banner status="error" title={catalogError} />}
      {next && (
        <Button
          label="Load more history sources"
          isLoading={loading}
          onClick={() => setAfter(next)}
        />
      )}
      {!current && (
        <EmptyState
          title={
            loading ? "Loading history sources" : "No retained metric evidence"
          }
          isCompact
        />
      )}
      {selectedMetric && current && (
        <Trend
          key={`${current.id}:${selectedMetric}:${hours}`}
          kind={current.apiKind}
          entity={current.id}
          metric={selectedMetric}
          hours={hours}
          refresh={refresh}
        />
      )}
    </Stack>
  );
}
export function DiagnosticsPage({ snapshot, stack }: PageProps) {
  const [downloadError, setDownloadError] = useState("");
  async function download() {
    try {
      const bundle = await api<Snapshot>("diagnostics");
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(bundle, null, 2)], {
          type: "application/json",
        }),
      );
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "agentic-ocudu-spark-diagnostics.json";
      anchor.click();
      URL.revokeObjectURL(url);
      setDownloadError("");
    } catch {
      setDownloadError("Unable to create the redacted diagnostic export");
    }
  }
  const observations = snapshot.observations.filter(
    (item) =>
      (item.entity === stack ||
        item.entity.startsWith(`${stack}:`) ||
        item.entity === "spark") &&
      (item.status !== "ok" || item.reason),
  );
  return (
    <Stack className="spark-page" gap={4}>
      <PageIntro
        title="Diagnostics"
        description="Collector evidence, unavailable fields, and a redacted support export."
        icon={Settings}
      />
      <Stack
        className="page-actions"
        gap={3}
        direction="horizontal"
        align="center"
        justify="between"
        wrap="wrap"
      >
        <Button
          onClick={download}
          label={"Download redacted snapshot"}
          icon={<Download />}
        ></Button>
      </Stack>
      {downloadError && <Banner status="error" title={downloadError} />}
      <Card className="section-frame detail-panel">
        <Stack gap={4}>
          <Stack
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Heading level={2}>Host evidence</Heading>
          </Stack>
          <Details
            values={
              snapshot.components?.find((item) => item.id === "spark")
                ?.details || { host_evidence: "unavailable" }
            }
          />
        </Stack>
      </Card>
      <Card className="table-section">
        <Stack gap={4}>
          <Stack
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Heading level={2}>Evidence requiring attention</Heading>
            <span className="section-meta">{observations.length} records</span>
          </Stack>
          <Stack className="diagnostics" gap={4}>
            {observations.map((item) => (
              <Stack key={item.entity + item.name} gap={4}>
                <span>
                  {item.entity} / {names[item.name] || text(item.name)}
                </span>
                <Badge state={item.status} />
                <span title={item.reason || ""}>{text(item.reason || "")}</span>
              </Stack>
            ))}
            {!observations.length && (
              <EmptyState
                title="No unavailable or qualified evidence"
                isCompact
              />
            )}
          </Stack>
        </Stack>
      </Card>
      <Collapsible
        className="inline-disclosure"
        trigger={"Optional ext-DN ICMP diagnostics \u00B7 measured from Spark"}
      >
        {snapshot.devices
          ?.filter(
            (item) => item.stack === stack && item.reachability?.observed_at,
          )
          .map((item) => (
            <Stack key={item.id} gap={4}>
              <Heading level={3}>
                <Link href={`/devices/${encodeURIComponent(item.id)}`}>
                  {item.identity}
                </Link>
              </Heading>
              <Details
                values={{
                  measurement_point: "Spark ext-DN container",
                  target: "UE address reported by Open5GS",
                  result: text(item.reachability?.state || "unknown"),
                  reason: text(item.reachability?.reason || ""),
                  sampled_at: when(item.reachability?.observed_at),
                }}
              />
            </Stack>
          ))}
        {!snapshot.devices?.some(
          (item) => item.stack === stack && item.reachability?.observed_at,
        ) && (
          <EmptyState
            title="No diagnostic samples. ICMP probing is disabled by default."
            isCompact
          />
        )}
      </Collapsible>
    </Stack>
  );
}
export function OperationsPage({ csrf, refresh }: PageProps) {
  const [items, setItems] = useState<ControlTask[]>([]);
  const [selected, setSelected] = useState<ControlTask["action"] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [cancelling, setCancelling] = useState<string | null>(null);
  const active = items.find((item) =>
    ["queued", "running", "cancel_requested"].includes(item.state),
  );
  useEffect(() => {
    let alive = true;
    const load = () =>
      api<{
        items: ControlTask[];
      }>("control?limit=50")
        .then((result) => {
          if (alive) {
            setItems(result.items);
            setLoadError("");
          }
        })
        .catch(() => {
          if (alive) setLoadError("Unable to load stack control history");
        });
    load();
    const timer = window.setInterval(load, active ? 1000 : 5000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [refresh, active?.id, active?.state]);
  async function submit() {
    if (!selected || busy || cancelling || active) return;
    setError("");
    setBusy(true);
    try {
      const task = await api<ControlTask>("control", {
        method: "POST",
        headers: { "X-CSRF-Token": csrf },
        body: JSON.stringify({ action: selected, confirmation: true }),
      });
      setItems((current) => [task, ...current]);
      setSelected(null);
      setError("");
    } catch (exc) {
      setError(text((exc as Error).message));
    } finally {
      setBusy(false);
    }
  }
  async function cancel(id: string) {
    if (busy || cancelling) return;
    setCancelling(id);
    setError("");
    try {
      const task = await api<ControlTask>(`control/${id}/cancel`, {
        method: "POST",
        headers: { "X-CSRF-Token": csrf },
      });
      setItems((current) =>
        current.map((item) => (item.id === id ? task : item)),
      );
    } catch (exc) {
      setError(text((exc as Error).message));
    } finally {
      setCancelling(null);
    }
  }
  return (
    <Stack className="spark-page" gap={4}>
      <PageIntro
        title="Stack operations"
        description="Bounded control for the independent OpenAirKit 5G SA protocol stack."
        icon={Settings}
      />
      <Card className="section-frame operations-panel">
        <Stack gap={4}>
          <Stack
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Heading level={2}>Independent stack control</Heading>
            <span className="section-meta">OCUDU · Open5GS · data only</span>
          </Stack>
          <Text as="p">
            Start, stop, or restart only the OpenAirKit 5G SA stack. The monitoring
            platform remains available after a stack stop.
          </Text>
          <Stack
            className="control-actions"
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Button
              onClick={() => {
                setError("");
                setSelected("start");
              }}
              label={"Start"}
              icon={<Play />}
              isDisabled={Boolean(active) || busy || Boolean(cancelling)}
            ></Button>
            <Button
              onClick={() => {
                setError("");
                setSelected("stop");
              }}
              label={"Stop"}
              icon={<Square />}
              isDisabled={Boolean(active) || busy || Boolean(cancelling)}
            ></Button>
            <Button
              onClick={() => {
                setError("");
                setSelected("restart");
              }}
              label={"Restart"}
              icon={<RotateCcw />}
              isDisabled={Boolean(active) || busy || Boolean(cancelling)}
            ></Button>
          </Stack>
          <AlertDialog
            isOpen={Boolean(selected)}
            onOpenChange={(open) => {
              if (!open && !busy) setSelected(null);
            }}
            title={
              error
                ? "Operation could not be submitted"
                : "Confirm stack operation"
            }
            description={`Confirm ${selected || "operation"}. This interrupts active UE sessions. Jetson must reconnect after the radio returns.${error ? ` Error: ${error}` : ""}${active ? " Another operation is now in progress. Close this dialog and review its status." : ""}`}
            cancelLabel="Back"
            actionLabel="Confirm"
            isActionLoading={busy}
            onAction={submit}
          />
          {loadError && <Banner status="warning" title={loadError} />}
          {error && !selected && (
            <Banner
              status="error"
              title={error}
              isDismissable
              onDismiss={() => setError("")}
            />
          )}
        </Stack>
      </Card>
      <Card className="table-section">
        <Stack gap={4}>
          <Stack
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Heading level={2}>Operation history</Heading>
            <span className="section-meta">30-day retention</span>
          </Stack>
          <Stack className="operation-list" gap={4}>
            {items.map((item) => (
              <Stack
                className={`control-task ${item.state}`}
                key={item.id}
                gap={4}
              >
                <Stack gap={4}>
                  <Text weight="semibold">
                    {text(item.action)} · <Badge state={item.state} />
                  </Text>
                  <Text type="supporting" color="secondary">
                    {when(item.updated_at)}
                  </Text>
                </Stack>
                <Table
                  data={item.steps}
                  columns={[
                    {
                      key: "name",
                      header: "Step",
                      width: proportional(2),
                      renderCell: (step) => text(step.name),
                    },
                    {
                      key: "state",
                      header: "State",
                      width: proportional(1),
                      renderCell: (step) => <Badge state={step.state} />,
                    },
                  ]}
                />
                {item.error && <Text as="p">{text(item.error)}</Text>}
                {["queued", "running"].includes(item.state) && (
                  <Button
                    onClick={() => cancel(item.id)}
                    label={"Cancel at next safe boundary"}
                    isLoading={cancelling === item.id}
                    isDisabled={busy || Boolean(cancelling)}
                    icon={<XCircle />}
                  ></Button>
                )}
              </Stack>
            ))}
            {!items.length && (
              <EmptyState title="No stack operations recorded" isCompact />
            )}
          </Stack>
        </Stack>
      </Card>
    </Stack>
  );
}
