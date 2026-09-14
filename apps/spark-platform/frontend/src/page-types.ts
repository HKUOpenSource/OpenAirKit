import type { Snapshot } from "./types";

export type PageProps = {
  snapshot: Snapshot;
  stack: string;
  refresh: number;
  csrf: string;
};
