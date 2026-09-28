import { api } from "./api";
import type { MetricPoint } from "./types";
export type HistoryEntry = {
  refreshed: number;
  request: Promise<MetricPoint[]>;
};
export function requestHistory(
  cache: Map<string, HistoryEntry>,
  kind: string,
  entity: string,
  hours: number,
  refresh: number,
) {
  const key = `${kind}:${entity}:${hours}`;
  const existing = cache.get(key);
  if (existing?.refreshed === refresh) return existing.request;
  const since = new Date(Date.now() - hours * 3600000).toISOString();
  const request = api<{ items: MetricPoint[] }>(
    `${kind}/${encodeURIComponent(entity)}/metrics?since=${since}&bucket=${Math.max(5, Math.ceil((hours * 3600) / 360))}`,
  ).then((result) => result.items);
  if (cache.size >= 64) cache.delete(cache.keys().next().value!);
  cache.set(key, { refreshed: refresh, request });
  request.catch(() => {
    if (cache.get(key)?.request === request) cache.delete(key);
  });
  return request;
}
