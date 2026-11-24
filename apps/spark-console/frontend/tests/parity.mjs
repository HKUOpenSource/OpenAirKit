import { chromium } from "playwright";
import assert from "node:assert/strict";
import fs from "node:fs/promises";

const base = process.env.AOC_TEST_URL || "http://127.0.0.1:4173";
const at = new Date().toISOString();
const metric = (entity, name, value, unit = "count", status = "ok") => ({
  source: "fixture",
  entity,
  name,
  value,
  unit,
  status,
  reason: null,
  observed_at: at,
});
const session = {
  id: "1",
  dnn: "oai",
  address: "10.0.0.33",
  sst: 1,
  sd: null,
  five_qi: 9,
  qfi: 1,
  pool_valid: true,
  n3_verified: true,
  state: "active",
  status: "ok",
  source: "open5gs_info",
  observed_at: at,
};
const subscriber = {
  id: "ocudu:ue:masked",
  stack: "ocudu",
  identity: "001010000000137",
  identifiers: { ran_ue_ngap_id: "17", amf_ue_ngap_id: "42" },
  registration: "registered",
  state: "registered",
  status: "ok",
  source: "amf_smf_supi",
  correlation: "amf_smf_supi",
  first_seen: at,
  observed_at: at,
  sessions: [session],
  metrics: [],
  connection: {
    state: "registered",
    reason: "registration_not_data_connectivity",
    layers: {
      registration: "registered",
      radio: "unverified",
      data_pdu: "recent_report",
    },
  },
};
const radio = {
  id: "ocudu:radio:44",
  stack: "ocudu",
  identity: "RNTI 0044",
  identifiers: { rnti: "0044", pci: 666 },
  registration: "unknown",
  state: "radio_observed",
  status: "ok",
  source: "ocudu_scheduler",
  correlation: "radio_only",
  first_seen: at,
  observed_at: at,
  sessions: [],
  metrics: [
    metric("ocudu:radio:44", "phr", 28, "dB"),
    metric("ocudu:radio:44", "dl_bps", 58000000, "bit/s"),
    metric("ocudu:radio:44", "ul_bps", 11000000, "bit/s"),
  ],
  connection: {
    state: "radio_observed",
    reason: "radio_context_not_subscriber_connection",
    layers: {
      registration: "unknown",
      radio: "radio_observed",
      data_pdu: "unverified",
    },
  },
};
const component = (role, health = "healthy") => ({
  id: `ocudu:${role}`,
  stack: "ocudu",
  name: role === "gnb" ? "OCUDU gNB" : role.toUpperCase(),
  kind: role === "gnb" ? "ran" : "nf",
  state: "running",
  health,
  business_health: health,
  status: "ok",
  observed_at: at,
  details: {
    health_reason:
      role === "gnb"
        ? "process_usb_owner_and_n2_verified"
        : "Container health check",
    restarts: 0,
    ...(role === "gnb"
      ? {
          source_commit: "050a2bb",
          release_id: "v2",
          executable: "/opt/agentic-ocudu/gnb",
          srate: 23.04,
          tx_gain: 80,
          rx_gain: 68,
          nof_antennas_dl: 1,
          nof_antennas_ul: 1,
          band: 78,
          dl_arfcn: 643392,
          channel_bandwidth_MHz: 20,
          common_scs: 30,
        }
      : {}),
  },
  metrics: [
    metric(`ocudu:${role}`, "cpu_utilization", 0.21, "ratio"),
    metric(`ocudu:${role}`, "cpu_cores", 1.7, "cores"),
    metric(`ocudu:${role}`, "cpu_capacity", 20, "cores"),
    metric(`ocudu:${role}`, "cpu_host_share", 0.085, "ratio"),
    metric(`ocudu:${role}`, "memory_used", 850000000, "byte"),
    metric(`ocudu:${role}`, "dl_bps", 58000000, "bit/s"),
    metric(`ocudu:${role}`, "ul_bps", 11000000, "bit/s"),
    metric(`ocudu:${role}`, "cqi", 14),
    metric(`ocudu:${role}`, "log_underflows", 0),
  ],
});
const link = (name) => ({
  id: `ocudu:${name}`,
  stack: "ocudu",
  name: name.toUpperCase(),
  kind: "link",
  state: "healthy",
  status: "ok",
  observed_at: at,
  details: {
    evidence:
      name === "n2"
        ? "sctp_association"
        : name === "n4"
          ? "pfcp_association"
          : "independent_ip_counters",
  },
  metrics: [
    metric(`ocudu:${name}`, "downlink_bps", 35000000, "bit/s"),
    metric(`ocudu:${name}`, "uplink_bps", 7800000, "bit/s"),
  ],
});
const snapshot = {
  schema_version: 4,
  observed_at: at,
  collector_status: "ok",
  active_stack: "ocudu",
  health: {
    ocudu: {
      host: "healthy",
      b210: "healthy",
      ran: "healthy",
      core: "healthy",
    },
  },
  services: [],
  components: [
    {
      id: "spark",
      stack: "host",
      name: "DGX Spark",
      kind: "host",
      state: "healthy",
      status: "ok",
      observed_at: at,
      details: { cpu_capacity: 20 },
      metrics: [],
    },
    component("gnb"),
    ...["nrf", "amf", "smf", "upf", "ausf", "udm", "udr"].map((role) =>
      component(role),
    ),
  ],
  links: ["n2", "n3", "n4", "n6"].map(link),
  devices: [subscriber, radio],
  observations: [
    metric("spark", "cpu_usage", 0.24, "ratio"),
    metric("spark", "memory_used", 18000000000, "byte"),
    metric("spark", "memory_total", 128000000000, "byte"),
    metric("spark", "disk_used", 90000000000, "byte"),
    metric("spark", "disk_total", 1000000000000, "byte"),
    metric("spark", "temperature", 51, "C"),
    metric("spark", "host_rx", 1800000, "bit/s"),
    metric("spark", "host_tx", 900000, "bit/s"),
    metric("ocudu", "b210_speed", 5000),
    metric("ocudu", "n2_associated", true),
    metric("ocudu", "radio_contexts", 1),
    metric("ocudu", "restarts", 0),
  ],
};
const events = [
  {
    id: "e1",
    at,
    stack: "ocudu",
    entity: "ocudu:gnb",
    level: "info",
    kind: "radio_state",
    message: "Radio and N2 evidence verified",
  },
  {
    id: "e2",
    at,
    stack: "ocudu",
    entity: subscriber.id,
    level: "info",
    kind: "device_change",
    message: "Registration and session evidence changed",
  },
];

await fs.mkdir("../../../artifacts/monitor-browser", { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    let authenticated = false;
    await page.addInitScript(() => {
      window.EventSource = class extends EventTarget {
        constructor() {
          super();
          window.testStream = this;
        }
        close() {}
      };
    });
    await page.route("**/api/v1/**", (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      if (path.endsWith("/session"))
        return authenticated
          ? route.fulfill({ json: { csrf: "fixture" } })
          : route.fulfill({ status: 401, json: { detail: "login_required" } });
      if (path.endsWith("/login")) {
        authenticated = true;
        return route.fulfill({ json: { csrf: "fixture" } });
      }
      if (path.endsWith("/snapshot")) return route.fulfill({ json: snapshot });
      if (path.endsWith("/events/kinds"))
        return route.fulfill({
          json: { items: [...new Set(events.map((event) => event.kind))] },
        });
      if (path.endsWith("/history/catalog"))
        return route.fulfill({
          json: {
            items: [...snapshot.components, ...snapshot.links].map((item) => ({
              ...item,
              apiKind: "components",
            })),
            next_cursor: null,
          },
        });
      if (path.includes("/events"))
        return route.fulfill({ json: { items: events, next_cursor: null } });
      if (path.endsWith("/devices"))
        return route.fulfill({ json: { items: [subscriber, radio] } });
      if (path.includes("/devices/"))
        return route.fulfill({
          json: path.endsWith("/metrics")
            ? { items: [{ at, metrics: radio.metrics }] }
            : subscriber,
        });
      if (path.includes("/metrics"))
        return route.fulfill({
          json: { items: [{ at, metrics: component("gnb").metrics }] },
        });
      if (path.endsWith("/control"))
        return route.fulfill({ json: { items: [] } });
      if (path.endsWith("/diagnostics"))
        return route.fulfill({ json: snapshot });
      if (path.endsWith("/logout"))
        return route.fulfill({ json: { ok: true } });
      return route.fulfill({ json: {} });
    });
    await page.goto(base);
    await page.getByLabel("Administrator password").fill("fixture");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page
      .getByRole("heading", { name: "Overview", exact: true })
      .waitFor();
    if (viewport.width <= 760)
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
    const nav = primaryNavigation(page, viewport.width).getByRole("link");
    assert.deepEqual(await nav.allTextContents(), [
      "Overview",
      "gNB",
      "Core Network",
      "Devices",
      "Events",
      "Metric history",
      "Operations",
      "Diagnostics",
    ]);
    if (viewport.width <= 760) {
      await page.keyboard.press("Escape");
      await page
        .getByRole("dialog", { name: "Navigation", exact: true })
        .waitFor({ state: "hidden" });
    }
    assert.equal(await page.locator(".spark-topology-node").count(), 7);
    assert.deepEqual(
      await page.locator(".devices-preview th").allTextContents(),
      ["Identity", "State", "PDU addresses", "DNNs", "Last seen"],
    );
    assert.equal(
      await page.locator(".devices-preview td").first().innerText(),
      subscriber.identity,
    );
    assert.equal(
      await page.locator(".devices-preview .source-label").count(),
      0,
    );

    if (viewport.width <= 760) {
      assert.equal(
        await page.locator(".devices-preview table").evaluate((table) => {
          const scroller = table.closest('[role="group"]');
          return (
            table.querySelector("td").getBoundingClientRect().width >= 100 &&
            scroller.scrollWidth > scroller.clientWidth &&
            scroller.tabIndex === 0
          );
        }),
        true,
        "Mobile device table keeps readable columns in its keyboard-accessible scroller",
      );
    }
    for (const title of [
      "Host resources",
      "Core network",
      "Attached devices",
      "Recent events",
    ])
      await page.getByRole("heading", { name: title, exact: true }).waitFor();
    assert.equal(
      await page
        .getByRole("heading", {
          name: "Independent stack control",
          exact: true,
        })
        .count(),
      0,
    );
    await page.screenshot({
      path: `../../../artifacts/monitor-browser/layout-parity-${viewport.width}.png`,
      fullPage: true,
    });
    if (viewport.width <= 760)
      await page.getByRole("button", { name: "Open navigation" }).click();
    await primaryNavigation(page, viewport.width)
      .getByRole("link", { name: "gNB", exact: true })
      .click();
    await page
      .getByRole("button", {
        name: "Runtime, RF configuration and hardware",
        exact: true,
      })
      .click();
    await page
      .getByRole("heading", { name: "RF configuration", exact: true })
      .waitFor();
    await page.goto(base + "/ran");
    await page.waitForURL("**/gnb");
    await page.goto(base + "/core");
    await page
      .getByRole("heading", { name: "User-plane traffic", exact: true })
      .waitFor();
    await page.getByRole("button", { name: "SMF", exact: true }).click();
    await page
      .getByRole("heading", { name: "SMF details", exact: true })
      .waitFor();
    await page.goto(base + "/devices");
    await choose(page, "Data PDU", "Active data PDU");
    await page.getByText("001010000000137", { exact: true }).waitFor();
    await page
      .getByRole("link", { name: "001010000000137", exact: true })
      .first()
      .click();
    await page
      .getByRole("heading", { name: "PDU sessions", exact: true })
      .waitFor();
    assert.equal(await page.getByText("Connected", { exact: true }).count(), 0);
    await page.goto(base + "/events");
    await choose(page, "Event level", "Info");
    await page.getByRole("link", { name: "View metric history" }).click();
    await page.waitForURL("**/history");
    if (viewport.width <= 760)
      await page.getByRole("button", { name: "Open navigation" }).click();
    await primaryNavigation(page, viewport.width)
      .getByRole("link", { name: "Operations", exact: true })
      .click();
    await page
      .getByRole("heading", { name: "Independent stack control", exact: true })
      .waitFor();
    await page.getByRole("button", { name: "Start", exact: true }).click();
    await page
      .getByRole("alertdialog", { name: "Confirm stack operation" })
      .waitFor();
    await page.getByRole("button", { name: "Back", exact: true }).click();
    await page.evaluate(() => window.testStream.onerror());
    await page.waitForFunction(() =>
      document
        .querySelector(".collection-status")
        ?.textContent.includes("Evidence stale"),
    );
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
    assert.deepEqual(errors, []);
    await page.close();
  }
  console.log(
    "Primary navigation, responsive layout, safe device state, secondary tools, legacy routes and stale evidence passed",
  );
} finally {
  await browser.close();
}

async function choose(page, label, option) {
  await page.getByRole("combobox", { name: label, exact: true }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

function primaryNavigation(page, width) {
  return width <= 760
    ? page.getByRole("dialog", { name: "Navigation", exact: true })
    : page.getByRole("navigation", { name: "Primary navigation", exact: true });
}
