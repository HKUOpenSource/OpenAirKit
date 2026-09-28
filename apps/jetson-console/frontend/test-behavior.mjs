import test from "node:test";
import assert from "node:assert/strict";
import { build } from "esbuild";
async function load(entry) {
  const { outputFiles } = await build({
    entryPoints: [new URL(entry, import.meta.url).pathname],
    bundle: true,
    write: false,
    platform: "node",
    format: "esm",
  });
  return import(
    `data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString("base64")}`
  );
}
const { confirmOperation } = await load("./src/operations.ts");
const reply = (body) => new Response(JSON.stringify(body));
test("recovery retry reuses the prepared task after a failed run request", async () => {
  const requests = [];
  let pending = { kind: "recover", params: {} };
  globalThis.fetch = async (url, options) => {
    requests.push([url, options.method]);
    if (url.endsWith("/jobs")) return reply({ id: "task-1", state: "ready" });
    if (url.endsWith("/run")) throw Error("response lost");
    return reply({ id: "task-1", state: "running" });
  };
  const created = (jobId) => {
    pending = { ...pending, jobId };
  };
  await assert.rejects(
    confirmOperation(pending, "revision", created),
    /response lost/,
  );
  await confirmOperation(pending, "revision", created);
  assert.deepEqual(requests, [
    ["/api/v1/jobs", "POST"],
    ["/api/v1/jobs/task-1/run", "POST"],
    ["/api/v1/jobs/task-1", "GET"],
  ]);
});
test("a prepared setup plan is never automatically executed", async () => {
  const requests = [];
  globalThis.fetch = async (url) => {
    requests.push(url);
    return reply({ id: "setup-1", state: "ready" });
  };
  await confirmOperation(
    { kind: "setup", params: { mode: "manual" } },
    "revision",
    () => {},
  );
  assert.deepEqual(requests, ["/api/v1/jobs"]);
});
test("a retry starts the same ready recovery task without creating another", async () => {
  const requests = [];
  globalThis.fetch = async (url) => {
    requests.push(url);
    return reply({ id: "task-1", state: "ready" });
  };
  await confirmOperation(
    { kind: "recover", params: {}, jobId: "task-1" },
    "revision",
    () => {},
  );
  assert.deepEqual(requests, [
    "/api/v1/jobs/task-1",
    "/api/v1/jobs/task-1/run",
  ]);
});
