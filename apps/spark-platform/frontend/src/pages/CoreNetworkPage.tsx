import {
  Button,
  Card,
  EmptyState,
  Grid,
  Heading,
  Link,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
} from "@astryxdesign/core";
import { Boxes, CircuitBoard, Network, Server, Waypoints } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge, Trend, text, value } from "../components";
import type { PageProps } from "../page-types";
import { DetailRows, PageIntro, SummaryItem } from "../page-ui";
import type { Component } from "../types";
export function CoreNetworkPage({ snapshot, stack, refresh }: PageProps) {
  const components =
    snapshot.components?.filter(
      (item) => item.stack === stack && item.kind === "nf",
    ) || [];
  const [selected, setSelected] = useState("");
  const component = useMemo(
    () => components.find((item) => item.id === selected) || components[0],
    [components, selected],
  );
  useEffect(() => {
    if (component && !selected) setSelected(component.id);
  }, [component, selected]);
  const links = snapshot.links?.filter((item) => item.stack === stack) || [];
  const bridge = snapshot.components?.find(
    (item) => item.id === `${stack}:bridge`,
  );
  const healthy = components.filter(
    (item) => (item.business_health || item.health) === "healthy",
  ).length;
  const verified = links.filter(
    (item) =>
      item.state === "healthy" &&
      item.details.evidence &&
      item.details.evidence !== "independent_ip_counters",
  ).length;
  return (
    <Stack className="spark-page" gap={4}>
      <PageIntro
        title="Open5GS Core Network"
        description="Container services, network functions, resource use, and protocol links."
        icon={Boxes}
      />
      <Grid
        className="summary-strip"
        columns={{ minWidth: 180, repeat: "fit" }}
        gap={4}
      >
        <SummaryItem icon={Server} label="Network functions">
          {components.length}
        </SummaryItem>
        <SummaryItem icon={CircuitBoard} label="Healthy services">
          {healthy}
        </SummaryItem>
        <SummaryItem icon={Waypoints} label="Verified links">
          {verified} / {links.length}
        </SummaryItem>
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
            <Heading level={2}>Network functions</Heading>
            <span className="section-meta">{healthy} healthy</span>
          </Stack>
          <Stack className="table-scroll" gap={4}>
            <Table className="selectable-table" style={{ minWidth: 840 }}>
              <TableHeader>
                <TableRow isHeaderRow>
                  <TableHeaderCell>Network function</TableHeaderCell>
                  <TableHeaderCell>Runtime</TableHeaderCell>
                  <TableHeaderCell>Health</TableHeaderCell>
                  <TableHeaderCell>CPU cores used</TableHeaderCell>
                  <TableHeaderCell>Memory</TableHeaderCell>
                  <TableHeaderCell>Restarts</TableHeaderCell>
                  <TableHeaderCell></TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {components.map((item) => (
                  <TableRow
                    key={item.id}
                    className={item.id === component?.id ? "selected-row" : ""}
                    onClick={() => setSelected(item.id)}
                  >
                    <TableCell>
                      <Button
                        onClick={() => setSelected(item.id)}
                        label={item.name}
                      ></Button>
                    </TableCell>
                    <TableCell>
                      <Badge state={item.state} />
                    </TableCell>
                    <TableCell>
                      <Badge
                        state={item.business_health || item.health || "unknown"}
                      />
                    </TableCell>
                    <TableCell>
                      {value(
                        item.metrics.find(
                          (metric) => metric.name === "cpu_cores",
                        ),
                      )}
                    </TableCell>
                    <TableCell>
                      {value(
                        item.metrics.find(
                          (metric) => metric.name === "memory_used",
                        ),
                      )}
                    </TableCell>
                    <TableCell>
                      {String(item.details.restarts ?? "—")}
                    </TableCell>
                    <TableCell>
                      <Link
                        aria-label={`Open ${item.name} details`}
                        href={`/components/${encodeURIComponent(item.id)}`}
                      >
                        ›
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {!components.length && (
              <EmptyState title="No network function evidence" isCompact />
            )}
          </Stack>
        </Stack>
      </Card>
      <Card className="link-strip" aria-label="Core network interfaces">
        <Grid columns={{ minWidth: 180, repeat: "fit" }} gap={4}>
          {links.map((item) => (
            <Stack key={item.id} gap={4}>
              <Network />
              <Stack gap={1}>
                <Text weight="semibold">{item.name}</Text>
                <Text type="supporting" color="secondary">
                  {text(
                    String(item.details.evidence || "Evidence unavailable"),
                  )}
                </Text>
              </Stack>
              <Badge state={item.state} />
            </Stack>
          ))}
          {bridge && (
            <Stack gap={4}>
              <Network />
              <Stack gap={1}>
                <Text weight="semibold">CN bridge</Text>
                <Text type="supporting" color="secondary">
                  Diagnostic interface counters
                </Text>
              </Stack>
              <Badge state={bridge.status || "unknown"} />
            </Stack>
          )}
        </Grid>
      </Card>
      <Card className="user-plane-section">
        <Stack gap={4}>
          <Stack
            gap={3}
            direction="horizontal"
            align="center"
            justify="between"
            wrap="wrap"
          >
            <Stack gap={4}>
              <Heading level={2}>User-plane traffic</Heading>
              <Text as="p">
                N3, N6, and bridge values describe separate boundaries and are
                never added together.
              </Text>
            </Stack>
          </Stack>
          <Stack className="user-plane-summary" gap={4}>
            <TrafficBoundary
              title="N3 GTP-U"
              component={findLink(links, "n3")}
            />
            <TrafficBoundary
              title="N6 payload"
              component={findLink(links, "n6")}
            />
            <TrafficBoundary title="CN bridge" component={bridge} diagnostic />
          </Stack>
          <Grid
            className="chart-grid user-plane-charts"
            columns={{ minWidth: 320, repeat: "fit" }}
            gap={4}
          >
            {["n3", "n6"].flatMap((name) =>
              ["downlink_bps", "uplink_bps"].map((metric) => (
                <Trend
                  key={name + metric}
                  entity={`${stack}:${name}`}
                  metric={metric}
                  title={`${name.toUpperCase()} · ${metric === "downlink_bps" ? "Downlink" : "Uplink"}`}
                  refresh={refresh}
                />
              )),
            )}
          </Grid>
        </Stack>
      </Card>
      {component && (
        <Stack className="component-focus" gap={4}>
          <Card className="section-frame detail-panel">
            <Stack gap={4}>
              <Stack
                gap={3}
                direction="horizontal"
                align="center"
                justify="between"
                wrap="wrap"
              >
                <Heading level={2}>{component.name} details</Heading>
                <Badge
                  state={
                    component.business_health ||
                    component.health ||
                    component.state
                  }
                />
              </Stack>
              <DetailRows
                values={{
                  runtime_state: text(component.state),
                  health_reason: text(
                    String(
                      component.details.health_reason ||
                        "No health reason reported",
                    ),
                  ),
                  cpu_utilization: value(
                    component.metrics.find(
                      (item) => item.name === "cpu_utilization",
                    ),
                  ),
                  cpu_cores_used: value(
                    component.metrics.find((item) => item.name === "cpu_cores"),
                  ),
                  memory_used: value(
                    component.metrics.find(
                      (item) => item.name === "memory_used",
                    ),
                  ),
                  ...component.details,
                }}
              />
            </Stack>
          </Card>
          <Trend
            entity={component.id}
            metric="cpu_utilization"
            title={`${component.name} CPU utilization`}
            refresh={refresh}
          />
        </Stack>
      )}
    </Stack>
  );
}
function findLink(links: Component[], name: string) {
  return links.find(
    (item) => item.id === `ocudu:${name}` || item.name.toLowerCase() === name,
  );
}
function TrafficBoundary({
  title,
  component,
  diagnostic = false,
}: {
  title: string;
  component?: Component;
  diagnostic?: boolean;
}) {
  const first = component?.metrics.find(
    (item) => item.name === (diagnostic ? "bridge_rx" : "downlink_bps"),
  );
  const second = component?.metrics.find(
    (item) => item.name === (diagnostic ? "bridge_tx" : "uplink_bps"),
  );
  return (
    <Stack gap={4}>
      <Stack gap={1}>
        {title}
        {diagnostic && (
          <Text type="supporting" color="secondary">
            Diagnostic
          </Text>
        )}
      </Stack>
      <Text weight="semibold">{value(first)}</Text>
      <Text type="supporting" color="secondary">
        {diagnostic ? "Receive" : "Downlink"}
      </Text>
      <Text weight="semibold">{value(second)}</Text>
      <Text type="supporting" color="secondary">
        {diagnostic ? "Transmit" : "Uplink"}
      </Text>
    </Stack>
  );
}
