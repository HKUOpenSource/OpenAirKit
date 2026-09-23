export type Obj = Record<string, any>;
let csrf = "";

export async function api(path: string, body?: Obj): Promise<any> {
  const response = await fetch("/api/v1/" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const value = await response.json().catch(() => ({ detail: "Invalid server response" }));
  if (response.status === 401) window.dispatchEvent(new Event("session-expired"));
  if (!response.ok) throw new Error(value.detail || "Request failed");
  if (value.csrf) csrf = value.csrf;
  return value;
}

export async function download(path: string, filename: string) {
  const value = await api(path);
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export const terminal = (job: Obj | null) => !job || ["complete", "failed", "cancelled", "interrupted"].includes(job.state);
export const number = (value: unknown, digits = 1) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "--";
export const bitrate = (value: unknown) => typeof value === "number" ? number(value / 1e6) : "--";
export const when = (value: number) => value ? new Date(value * 1000).toLocaleString() : "Not observed";
