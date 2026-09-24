import { Chart, ChartAxis, line } from "@astryxdesign/charts";
import {
  proportional,
  Badge as AstryxBadge,
  Banner,
  Button,
  Card,
  EmptyState,
  Heading,
  MetadataList,
  MetadataListItem,
  ProgressBar,
  Stack,
  Table,
  Text,
} from "@astryxdesign/core";
import { Download, Play, Square } from "lucide-react";
import { api, download, number, Obj, terminal, when } from "./api";

export function Badge({ state = "unknown" }: { state?: string }) {
  const variant = [
    "ok",
    "active",
    "connected",
    "complete",
    "ready",
    "available",
    "live",
  ].includes(state)
    ? "success"
    : ["failed", "error", "blocked", "cancelled"].includes(state)
      ? "error"
      : [
            "warning",
            "degraded",
            "paused",
            "running",
            "cancelling",
            "stale",
          ].includes(state)
        ? "warning"
        : "neutral";
  return (
    <AstryxBadge
      style={{ alignSelf: "flex-start" }}
      className={"badge " + state}
      variant={variant}
      label={state.replaceAll("_", " ")}
    />
  );
}

export function Empty({
  children = "No records in this window",
}: {
  children?: string;
}) {
  return <EmptyState title={children} isCompact />;
}

export function Fields({ items }: { items: [string, React.ReactNode][] }) {
  return (
    <MetadataList columns="single">
      {items.map(([key, value]) => (
        <MetadataListItem key={key} label={key}>
          {value ?? "--"}
        </MetadataListItem>
      ))}
    </MetadataList>
  );
}

export function MiniChart({
  samples,
  field,
  label,
  unit,
}: {
  samples: Obj[];
  field: (sample: Obj) => number | null;
  label: string;
  unit: string;
}) {
  const data = samples
    .filter(
      (sample) => typeof sample.at === "number" && Number.isFinite(sample.at),
    )
    .map((sample) => {
      const value = field(sample);
      return {
        at: sample.at * 1000,
        value:
          typeof value === "number" && Number.isFinite(value) ? value : null,
      };
    })
    .sort((a, b) => a.at - b.at);
  const valid = data.filter(
    (item) => typeof item.value === "number" && Number.isFinite(item.value),
  );
  return (
    <Card className="chart-panel">
      <Stack gap={4}>
        <Stack
          direction="horizontal"
          justify="between"
          align="center"
          wrap="wrap"
        >
          <Heading level={2}>{label}</Heading>
          <Text>{valid.length ? number(valid.at(-1)?.value) : "--"}</Text>
        </Stack>
        <Text type="supporting" color="secondary">
          {unit}
        </Text>
        {valid.length ? (
          <Chart
            title={label + " history"}
            data={data}
            xKey="at"
            series={[
              line("value", { label: unit, curve: "linear", dots: true }),
            ]}
            height={220}
            yBaseline="data"
            axes={
              <>
                <ChartAxis
                  position="left"
                  tickFormat={(value) => String(value)}
                />
                <ChartAxis
                  position="bottom"
                  maxTicks={3}
                  tickFormat={(value) =>
                    new Date(Number(value)).toLocaleTimeString("en-GB", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  }
                />
              </>
            }
          />
        ) : (
          <Empty>No current samples</Empty>
        )}
      </Stack>
    </Card>
  );
}

export function JobPanel({
  job,
  refresh,
  error,
}: {
  job: Obj | null;
  refresh: () => void;
  error: (value: string) => void;
}) {
  if (!job)
    return (
      <Card>
        <Stack gap={4}>
          <Empty>No task has been created</Empty>
        </Stack>
      </Card>
    );
  async function perform(action: "run" | "cancel") {
    try {
      await api(
        `jobs/${job!.id}/${action}`,
        action === "run" ? { confirmed: true } : {},
      );
      refresh();
    } catch (reason) {
      error(String(reason));
    }
  }
  return (
    <Card className="job-panel">
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
            <Heading level={2}>
              {job.kind === "setup" ? "Device setup" : "Recovery"}
            </Heading>
            <Text type="supporting" color="secondary">
              Task {job.id.slice(0, 8)} · {when(job.created_at)}
            </Text>
          </Stack>
          <Badge state={job.state} />
        </Stack>
        <ProgressBar
          value={job.progress || 0}
          label="Task progress"
          hasValueLabel
        />
        <Table
          data={job.steps as Obj[]}
          idKey="id"
          columns={[
            { key: "id", header: "Step", width: proportional(2) },
            {
              key: "state",
              header: "State",
              width: proportional(1),
              renderCell: (step) => <Badge state={step.state} />,
            },
            {
              key: "error",
              header: "Detail",
              width: proportional(2),
              renderCell: (step) => step.error || "—",
            },
          ]}
        />
        {job.error ? <Banner status="error" title={job.error} /> : null}
        {job.cleanup ? (
          <Banner
            status="info"
            title="Cleanup"
            description={
              job.cleanup.error ||
              job.cleanup.reason ||
              JSON.stringify(job.cleanup)
            }
          />
        ) : null}
        <Stack
          className="actions"
          gap={3}
          direction="horizontal"
          align="center"
          justify="between"
          wrap="wrap"
        >
          {["ready", "paused"].includes(job.state) ? (
            <Button
              onClick={() => perform("run")}
              label={
                job.state === "paused" ? "Run next step" : "Confirm and run"
              }
              icon={<Play size={15} />}
              variant="primary"
            ></Button>
          ) : null}
          {!terminal(job) ? (
            <Button
              onClick={() => perform("cancel")}
              label={"Cancel"}
              icon={<Square size={15} />}
            ></Button>
          ) : null}
          <Button
            onClick={() =>
              download(
                `jobs/${job.id}`,
                `aoc-jetson-task-${job.id}.json`,
              ).catch((reason) => error(String(reason)))
            }
            label={"Report"}
            icon={<Download size={15} />}
          ></Button>
        </Stack>
      </Stack>
    </Card>
  );
}
