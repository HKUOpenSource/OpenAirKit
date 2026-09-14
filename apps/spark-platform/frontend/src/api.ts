export async function api<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api/v1/" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (response.status === 401 && path !== "login")
    window.dispatchEvent(new Event("aoc-auth-expired"));
  const data = await response.json();
  if (!response.ok)
    throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
  return data;
}
