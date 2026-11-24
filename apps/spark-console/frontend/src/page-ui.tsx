import { Banner, Card, Heading, Stack, Text } from "@astryxdesign/core";
import type { LucideIcon } from "lucide-react";
import { Badge, Details, text, value, when } from "./components";
import type { Observation } from "./types";

export function PageIntro({
  title,
  description,
  icon: Icon,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
}) {
  return (
    <Stack gap={2}>
      <Stack direction="horizontal" gap={3} align="center">
        <Icon size={20} />
        <Heading level={2}>{title}</Heading>
      </Stack>
      <Text color="secondary">{description}</Text>
    </Stack>
  );
}
export function StatusSummary({
  state,
  title,
  reason,
  updated,
}: {
  state: string;
  title: string;
  reason: string;
  updated: string;
}) {
  return (
    <Banner
      status={
        state === "healthy"
          ? "success"
          : state === "failed"
            ? "error"
            : "warning"
      }
      title={title}
      description={text(reason)}
      endContent={<Text type="supporting">Updated {when(updated)}</Text>}
    />
  );
}
export function SummaryItem({
  icon: Icon,
  label,
  children,
}: {
  icon: LucideIcon;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <Stack gap={3}>
        <Stack direction="horizontal" gap={2} align="center">
          <Icon size={18} />
          <Text color="secondary">{label}</Text>
        </Stack>
        <Text type="large" weight="semibold">
          {children}
        </Text>
      </Stack>
    </Card>
  );
}
export function DetailRows({ values }: { values: Record<string, unknown> }) {
  return <Details values={values} />;
}
export function MetricValue({ observation }: { observation?: Observation }) {
  return <>{value(observation)}</>;
}
export function EvidenceState({
  state,
  reason,
}: {
  state: string;
  reason?: unknown;
}) {
  return (
    <Stack gap={1}>
      <Badge state={state} />
      <Text type="supporting" color="secondary">
        {reason ? text(String(reason)) : "No supporting detail"}
      </Text>
    </Stack>
  );
}
