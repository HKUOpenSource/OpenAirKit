import {
  proportional,
  Banner,
  Button,
  Card,
  EmptyState,
  Heading,
  Link,
  Selector,
  Stack,
  Table,
} from "@astryxdesign/core";
import { RefreshCw, ScrollText } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Badge, text, when } from "../components";
import type { PageProps } from "../page-types";
import { PageIntro } from "../page-ui";
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
  const entities = useMemo(
    () =>
      [
        ...(snapshot.components || [])
          .filter((item) => item.stack === stack)
          .map((item) => ({ id: item.id, label: item.name })),
        ...(snapshot.links || [])
          .filter((item) => item.stack === stack)
          .map((item) => ({ id: item.id, label: item.name })),
        ...(snapshot.devices || [])
          .filter((item) => item.stack === stack)
          .map((item) => ({ id: item.id, label: item.identity })),
      ].filter(
        (item, index, all) =>
          all.findIndex((candidate) => candidate.id === item.id) === index,
      ),
    [snapshot, stack],
  );
  const kinds = useMemo(
    () => Array.from(new Set(items.map((item) => item.kind))).sort(),
    [items],
  );
  useEffect(() => {
    setCursor(null);
    setItems([]);
  }, [stack, level, entity, kind, hours]);
  useEffect(() => {
    const controller = new AbortController();
    const since = new Date(Date.now() - hours * 3600000).toISOString();
    const query = new URLSearchParams({
      stack,
      since,
      limit: String(PAGE_SIZE),
    });
    if (level) query.set("level", level);
    if (entity) query.set("entity", entity);
    if (kind) query.set("kind", kind);
    if (cursor) query.set("cursor", cursor);
    setBusy(true);
    api<{
      items: MonitoringEvent[];
      next_cursor: string | null;
    }>(`events?${query}`, { signal: controller.signal })
      .then((result) => {
        setItems((current) =>
          cursor
            ? [
                ...new Map(
                  [...current, ...result.items].map((item) => [item.id, item]),
                ).values(),
              ]
            : result.items,
        );
        setNext(result.next_cursor);
        setError("");
      })
      .catch((exc) => {
        if (exc.name !== "AbortError") setError("Unable to load events");
      })
      .finally(() => setBusy(false));
    return () => controller.abort();
  }, [stack, level, entity, kind, hours, cursor, refresh, reload]);
  return (
    <Stack className="spark-page" gap={4}>
      <PageIntro
        title="Monitoring events"
        description="State transitions and allow-listed diagnostics retained for 30 days."
        icon={ScrollText}
      />
      <Stack
        className="page-actions"
        gap={3}
        direction="horizontal"
        align="center"
        justify="between"
        wrap="wrap"
      >
        <Link className="secondary-button" href={"/history"}>
          View metric history
        </Link>
      </Stack>
      <Stack
        className="filter-bar events-filter"
        gap={3}
        direction="horizontal"
        align="center"
        justify="between"
        wrap="wrap"
      >
        <Selector
          label={"Event environment"}
          value={String(stack)}
          options={[{ value: String("ocudu"), label: "OCUDU" }]}
          isDisabled
        ></Selector>
        <Selector
          label={"Event component or device"}
          value={String(entity)}
          options={[
            { value: String(""), label: "All entities" },
            ...entities.map((item) => ({
              value: String(item.id),
              label: item.label,
            })),
          ]}
          onChange={(selected) => setEntity(selected)}
        ></Selector>
        <Selector
          label={"Event level"}
          value={String(level)}
          options={[
            { value: String(""), label: "All levels" },
            { value: String("info"), label: "Info" },
            { value: String("warning"), label: "Warning" },
            { value: String("error"), label: "Error" },
          ]}
          onChange={(selected) => setLevel(selected)}
        ></Selector>
        <Selector
          label={"Event type"}
          value={String(kind)}
          options={[
            { value: String(""), label: "All types" },
            ...kinds.map((item) => ({
              value: String(item),
              label: text(item),
            })),
          ]}
          onChange={(selected) => setKind(selected)}
        ></Selector>
        <Selector
          label={"Event time range"}
          value={String(hours)}
          options={[
            { value: String(1), label: "Last hour" },
            { value: String(24), label: "Last day" },
            { value: String(168), label: "Last seven days" },
          ]}
          onChange={(selected) => setHours(Number(selected))}
        ></Selector>
        <Button
          onClick={() => {
            setCursor(null);
            setItems([]);
            setReload((value) => value + 1);
          }}
          label={"Refresh events"}
          icon={<RefreshCw className={busy ? "spin" : ""} />}
          isIconOnly
          isDisabled={busy}
        ></Button>
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
            <Heading level={2}>Event history</Heading>
            <span className="section-meta">
              {items.length}
              {next ? "+" : ""} results
            </span>
          </Stack>
          <Table
            data={items}
            idKey="id"
            columns={[
              {
                key: "at",
                header: "Time",
                width: proportional(1),
                renderCell: (item) => when(item.at),
              },
              {
                key: "level",
                header: "Level",
                width: proportional(1),
                renderCell: (item) => <Badge state={item.level || "info"} />,
              },
              {
                key: "kind",
                header: "Type",
                width: proportional(1),
                renderCell: (item) => text(item.kind),
              },
              {
                key: "entity",
                header: "Source",
                width: proportional(1),
                renderCell: (item) =>
                  entities.find((candidate) => candidate.id === item.entity)
                    ?.label ||
                  item.entity ||
                  "—",
              },
              { key: "message", header: "Event", width: proportional(2) },
            ]}
            emptyState={
              <EmptyState
                title={busy ? "Loading events" : "No matching events"}
                isCompact
              />
            }
          />
          {next && (
            <Stack className="pagination-bar" gap={4}>
              <Button
                onClick={() => setCursor(next)}
                label={"Load older events"}
                isDisabled={busy}
              ></Button>
            </Stack>
          )}
        </Stack>
      </Card>
    </Stack>
  );
}
export function EventsPreview({
  stack,
  refresh,
}: {
  stack: string;
  refresh: number;
}) {
  const [items, setItems] = useState<MonitoringEvent[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    const since = new Date(Date.now() - 24 * 3600000).toISOString();
    api<{
      items: MonitoringEvent[];
    }>(`events?stack=${stack}&since=${since}&limit=6`, {
      signal: controller.signal,
    })
      .then((result) => setItems(result.items))
      .catch(() => setItems([]));
    return () => controller.abort();
  }, [stack, refresh]);
  return (
    <Card className="table-section events-preview">
      <Stack gap={4}>
        <Stack
          gap={3}
          direction="horizontal"
          align="center"
          justify="between"
          wrap="wrap"
        >
          <Heading level={2}>Recent events</Heading>
          <Link href={"/events"}>View history</Link>
        </Stack>
        <Table
          data={items}
          idKey="id"
          columns={[
            {
              key: "at",
              header: "Time",
              width: proportional(1),
              renderCell: (item) => when(item.at),
            },
            {
              key: "level",
              header: "Level",
              width: proportional(1),
              renderCell: (item) => <Badge state={item.level || "info"} />,
            },
            {
              key: "entity",
              header: "Source",
              width: proportional(1),
              renderCell: (item) => item.entity || item.kind,
            },
            { key: "message", header: "Event", width: proportional(2) },
          ]}
          emptyState={<EmptyState title="No monitoring events" isCompact />}
        />
      </Stack>
    </Card>
  );
}
