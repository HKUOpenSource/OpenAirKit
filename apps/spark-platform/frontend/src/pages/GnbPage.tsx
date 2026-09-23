import { Card, Collapsible, Grid, Heading, Stack } from "@astryxdesign/core";
import {
  Antenna,
  Cpu,
  Gauge,
  Radio,
  RefreshCw,
  Timer,
  UsersRound,
  Waypoints,
} from "lucide-react";
import { DeviceTable, Trend, value } from "../components";
import type { PageProps } from "../page-types";
import { DetailRows, PageIntro, StatusSummary, SummaryItem } from "../page-ui";
export function GnbPage({ snapshot, stack, refresh }: PageProps) {
  const component = snapshot.components?.find(
    (item) => item.id === `${stack}:gnb`,
  );
  const observations = [
    ...(component?.metrics || []),
    ...snapshot.observations.filter(
      (item) => item.entity === stack || item.entity === `${stack}:gnb`,
    ),
  ];
  const metric = (name: string) =>
    observations.find((item) => item.name === name);
  const runtimeFields = [
    "executable",
    "source_commit",
    "release_id",
    "pid",
    "invocation_id",
    "uptime",
    "restarts",
  ];
  const configFields = [
    "plmn",
    "tac",
    "pci",
    "band",
    "dl_arfcn",
    "absoluteFrequencySSB",
    "dl_absoluteFrequencyPointA",
    "channel_bandwidth_MHz",
    "dl_carrierBandwidth",
    "common_scs",
    "dl_subcarrierSpacing",
    "srate",
    "tx_gain",
    "rx_gain",
    "nof_antennas_dl",
    "nof_antennas_ul",
    "clock",
    "sync",
  ];
  const radioFields = [
    "b210_product",
    "b210_serial",
    "b210_speed",
    "b210_devices",
    "b210_holder_pids",
  ];
  const state =
    component?.health ||
    component?.business_health ||
    component?.state ||
    "unknown";
  return (
    <Stack className="spark-page" gap={4}>
      <PageIntro
        title="OCUDU gNB"
        description="Service, real-time scheduling, RF hardware, N2, and attached radio contexts."
        icon={Antenna}
      />
      <StatusSummary
        state={state}
        title={
          state === "healthy" ? "gNB is operating normally" : `gNB ${state}`
        }
        reason={String(
          component?.details.health_reason ||
            "Current radio evidence is unavailable",
        )}
        updated={snapshot.observed_at}
      />
      <Grid
        className="summary-strip gnb-summary"
        columns={{ minWidth: 180, repeat: "fit" }}
        gap={4}
      >
        <SummaryItem icon={Gauge} label="CPU utilization">
          {value(metric("cpu_utilization"))}
        </SummaryItem>
        <SummaryItem icon={Cpu} label="Used cores">
          {value(metric("cpu_cores"))} / {value(metric("cpu_capacity"))}
        </SummaryItem>
        <SummaryItem icon={Cpu} label="Host CPU share">
          {value(metric("cpu_host_share"))}
        </SummaryItem>
        <SummaryItem icon={UsersRound} label="Radio contexts">
          {value(metric("radio_contexts"))}
        </SummaryItem>
        <SummaryItem icon={Waypoints} label="N2 association">
          {value(metric("n2_associated"))}
        </SummaryItem>
        <SummaryItem icon={RefreshCw} label="Restarts">
          {value(metric("restarts"))}
        </SummaryItem>
        <SummaryItem icon={Radio} label="RX sample rate">
          {component?.details.srate != null
            ? `${component.details.srate} MSps`
            : "Unavailable"}
        </SummaryItem>
        <SummaryItem icon={Radio} label="TX sample rate">
          {component?.details.srate != null
            ? `${component.details.srate} MSps`
            : "Unavailable"}
        </SummaryItem>
      </Grid>
      <Grid
        className="monitor-grid"
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
              <Heading level={2}>Runtime</Heading>
              <Timer />
            </Stack>
            <DetailRows
              values={select(component?.details || {}, runtimeFields)}
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
              <Heading level={2}>RF configuration</Heading>
              <Antenna />
            </Stack>
            <DetailRows
              values={select(component?.details || {}, configFields)}
            />
            {component?.details.tdd != null && (
              <Collapsible
                className="inline-disclosure"
                trigger={"TDD configuration"}
              >
                <DetailRows
                  values={
                    typeof component.details.tdd === "object"
                      ? (component.details.tdd as Record<string, unknown>)
                      : { tdd: component.details.tdd }
                  }
                />
              </Collapsible>
            )}
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
              <Heading level={2}>Radio hardware</Heading>
              <Radio />
            </Stack>
            <DetailRows
              values={Object.fromEntries(
                radioFields.map((name) => [
                  name,
                  value(
                    snapshot.observations.find((item) => item.name === name),
                  ),
                ]),
              )}
            />
          </Stack>
        </Card>
      </Grid>
      <Grid
        className="chart-grid"
        columns={{ minWidth: 320, repeat: "fit" }}
        gap={4}
      >
        {[
          "cpu_utilization",
          "cpu_cores",
          "cpu_host_share",
          "memory_used",
          "dl_bps",
          "ul_bps",
          "dl_mcs",
          "ul_mcs",
          "cqi",
          "dl_bler",
          "ul_bler",
          "sinr",
          "log_underflows",
          "log_overflows",
          "log_lates",
        ].map((name) => (
          <Trend
            key={name}
            entity={`${stack}:gnb`}
            metric={name}
            refresh={refresh}
          />
        ))}
      </Grid>
      <Card className="table-section">
        <Stack gap={4}>
          <Stack
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Heading level={2}>Radio contexts</Heading>
            <span className="section-meta">
              {snapshot.devices?.filter(
                (item) =>
                  item.stack === stack && item.source === "ocudu_scheduler",
              ).length || 0}{" "}
              observed
            </span>
          </Stack>
          <DeviceTable
            radio
            devices={
              snapshot.devices?.filter(
                (item) =>
                  item.stack === stack && item.source === "ocudu_scheduler",
              ) || []
            }
          />
        </Stack>
      </Card>
    </Stack>
  );
}
function select(values: Record<string, unknown>, fields: string[]) {
  return Object.fromEntries(
    fields
      .filter((field) => field in values)
      .map((field) => [field, values[field]]),
  );
}
