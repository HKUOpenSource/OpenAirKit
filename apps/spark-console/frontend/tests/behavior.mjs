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
const { activeDataSession, freshDevice } = await load("../src/freshness.ts");
const { requestHistory } = await load("../src/history-client.ts");
const { api } = await load("../src/api.ts");
const now = Date.now();
const device = {
  status: "ok",
  registration: "registered",
  source: "open5gs_info",
  observed_at: new Date(now).toISOString(),
  metrics: [],
  sessions: [
    {
      dnn: "oai",
      state: "active",
      status: "ok",
      observed_at: new Date(now).toISOString(),
    },
  ],
};
test("only fresh active data PDU evidence counts as active", () => {
  assert.equal(activeDataSession(freshDevice(device, true, now)), true);
  for (const state of ["inactive", "unknown"]) {
    assert.equal(
      activeDataSession(
        freshDevice(
          { ...device, sessions: [{ ...device.sessions[0], state }] },
          true,
          now,
        ),
      ),
      false,
    );
  }
  assert.equal(activeDataSession(freshDevice(device, false, now)), false);
  assert.equal(
    activeDataSession(freshDevice(device, true, now + 91000)),
    false,
  );
  assert.equal(
    activeDataSession(
      freshDevice({ ...device, registration: "deregistered" }, true, now),
    ),
    false,
  );
  assert.equal(freshDevice(device, true, now).state, "registered");
});
test("15 charts share one entity/window request and refresh together", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    return new Response(JSON.stringify({ items: [] }));
  };
  const cache = new Map();
  await Promise.all(
    Array.from({ length: 15 }, () =>
      requestHistory(cache, "components", "ocudu:gnb", 1, 0),
    ),
  );
  assert.equal(calls, 1);
  await Promise.all(
    Array.from({ length: 15 }, () =>
      requestHistory(cache, "components", "ocudu:gnb", 1, 1),
    ),
  );
  assert.equal(calls, 2);
  await requestHistory(cache, "components", "ocudu:gnb", 24, 1);
  assert.equal(calls, 3);
  await requestHistory(new Map(), "components", "ocudu:gnb", 1, 1);
  assert.equal(calls, 4, "a new session must not reuse retained data");
});
test("a failed history request can be retried", async () => {
  const cache = new Map();
  globalThis.fetch = async () => {
    throw Error("offline");
  };
  await assert.rejects(requestHistory(cache, "components", "spark", 1, 0));
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ items: [{ at: "sample", metrics: [] }] }));
  assert.equal(
    (await requestHistory(cache, "components", "spark", 1, 0))[0].at,
    "sample",
  );
});
test("initial signed-out probe is distinct from session expiration", async () => {
  const target = new EventTarget();
  globalThis.window = target;
  let expired = 0;
  target.addEventListener("aoc-auth-expired", () => expired++);
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: "unauthorized" }), { status: 401 });
  await assert.rejects(api("session"));
  await assert.rejects(api("login"));
  assert.equal(expired, 0);
  await assert.rejects(api("snapshot"));
  assert.equal(expired, 1);
});
