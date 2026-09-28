import { api } from "./api";
import type { Obj } from "./api";
export type PendingOperation = { kind: string; params: Obj; jobId?: string };
// Preserve the task identity before starting it, including when the run response is lost.
export async function confirmOperation(
  pending: PendingOperation,
  revision: string,
  created: (id: string) => void,
) {
  const job = pending.jobId
    ? await api(`jobs/${pending.jobId}`)
    : await api("jobs", {
        kind: pending.kind,
        revision,
        params: pending.params,
      });
  created(job.id);
  if (pending.kind !== "setup" && ["ready", "paused"].includes(job.state))
    await api(`jobs/${job.id}/run`, { confirmed: true });
  return job;
}
