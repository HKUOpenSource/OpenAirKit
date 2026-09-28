import { createContext, useContext, useEffect, useRef, useState } from "react";
import { requestHistory, type HistoryEntry } from "./history-client";
import type { MetricPoint } from "./types";

const HistoryCache = createContext<Map<string, HistoryEntry> | null>(null);
export function HistoryProvider({ children }: { children: React.ReactNode }) {
  const cache = useRef(new Map<string, HistoryEntry>());
  return (
    <HistoryCache.Provider value={cache.current}>
      {children}
    </HistoryCache.Provider>
  );
}
export function useHistory(
  kind: string,
  entity: string,
  hours: number,
  refresh: number,
) {
  const cache = useContext(HistoryCache);
  const key = `${kind}:${entity}:${hours}`;
  const [result, setResult] = useState<{
    key: string;
    items: MetricPoint[];
    error: string;
  }>({ key: "", items: [], error: "" });
  useEffect(() => {
    let alive = true;
    const request = requestHistory(
      cache || new Map(),
      kind,
      entity,
      hours,
      refresh,
    );
    request
      .then((items) => {
        if (alive) setResult({ key, items, error: "" });
      })
      .catch(() => {
        if (alive)
          setResult({ key, items: [], error: "Unable to load history" });
      });
    return () => {
      alive = false;
    };
  }, [cache, kind, entity, hours, refresh, key]);
  return result.key === key ? result : { items: [], error: "" };
}
