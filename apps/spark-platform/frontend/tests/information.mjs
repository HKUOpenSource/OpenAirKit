import { chromium } from "playwright";
import assert from "node:assert/strict";

const base = process.env.AOC_TEST_URL || "http://127.0.0.1:8879";
const password = process.env.AOC_TEST_PASSWORD;
if (!password) throw new Error("AOC_TEST_PASSWORD is required");
const browser = await chromium.launch({ headless: true });
try {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.addInitScript(() => {
      window.EventSource = class extends EventTarget {
        constructor() {
          super();
          window.testStream = this;
        }
        close() {}
      };
    });
    const at = () => new Date().toISOString();
    const metric = (name, value, unit, status = "ok", observed_at = at()) => ({
      name,
      value,
      unit,
      status,
      observed_at,
      source: "test",
      entity: "spark",
      reason: null,
    });
    const old = new Date(Date.now() - 120000).toISOString();
    const state = {
      schema_version: 4,
      active_stack: "ocudu",
      collector_status: "ok",
      services: [],
      links: [],
      devices: [],
      observations: [],
      health: {
        ocudu: {
          host: "healthy",
          b210: "healthy",
          ran: "healthy",
          core: "healthy",
        },
      },
      components: [
        {
          id: "spark",
          stack: "host",
          name: "DGX Spark",
          kind: "host",
          state: "healthy",
          details: {},
          metrics: [metric("cpu_usage", 0.75, "ratio", "ok", old)],
        },
        {
          id: "ocudu:gnb",
          stack: "ocudu",
          name: "OCUDU gNB",
          kind: "ran",
          state: "active",
          health: "healthy",
          details: {
            health_reason: "process_usb_owner_and_n2_verified",
            srate: 23.04,
            channel_bandwidth_MHz: 20,
            executable: "/opt/gnb_file",
          },
          metrics: [metric("cqi", 12, "count")],
        },
        {
          id: "ocudu:n3",
          stack: "ocudu",
          name: "N3",
          kind: "link",
          state: "unknown",
          details: {},
          metrics: [
            metric("downlink_bps", 1000000, "bit/s"),
            metric("uplink_bps", 2000000, "bit/s"),
          ],
        },
      ],
    };
    let chartMode = "stale";
    await page.route("**/api/v1/snapshot", (route) =>
      route.fulfill({ json: { ...state, observed_at: at() } }),
    );
    await page.route("**/api/v1/**/metrics?*", (route) => {
      if (chartMode === "gaps") {
        const points = [
          [-90000, 0.1, "ok"],
          [-85000, 0.2, "ok"],
          [-80000, null, "unavailable"],
          [-75000, 0.3, "ok"],
          [-70000, 0.4, "ok"],
          [-10000, 0.5, "ok"],
          [-5000, 0.6, "ok"],
        ].map(([offset, value, status]) => {
          const time = new Date(Date.now() + offset).toISOString();
          return {
            at: time,
            metrics: [metric("cpu_usage", value, "ratio", status, time)],
          };
        });
        return route.fulfill({ json: { items: points } });
      }
      const points =
        chartMode === "stale"
          ? [
              {
                at: old,
                metrics: [metric("cpu_usage", 0.75, "ratio", "ok", old)],
              },
            ]
          : [{ at: at(), metrics: [metric("cpu_usage", 0.25, "ratio")] }];
      return route.fulfill({ json: { items: points } });
    });
    await page.goto(base);
    await page.getByLabel("Administrator password").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page
      .getByRole("heading", { name: "Overview", exact: true })
      .waitFor();
    if (width <= 760)
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
    assert.match(
      await page.locator(".system-state").innerText(),
      /All systems normal/,
    );
    if (width <= 760) await page.keyboard.press("Escape");
    assert.doesNotMatch(
      await page.getByRole("main").innerText(),
      /Jetson data|Jetson environment|Spark to UE address/,
    );
    await page.screenshot({
      path: `../../../artifacts/monitor-browser/information-${width}.png`,
      fullPage: true,
    });
    await page.goto(base + "/history");
    const chart = page.locator(".trend-section").filter({
      has: page.getByRole("heading", { name: "Host CPU", exact: true }),
    });
    await chart
      .getByTestId("current-metric")
      .filter({ hasText: "Stale" })
      .waitFor();
    assert.match(
      await chart.locator(".trend-evidence").innerText(),
      /Last valid: 75.0%/,
    );
    assert.equal(
      await chart.locator(".chart-axis > span").nth(1).innerText(),
      "%",
    );
    // Astryx measures its chart before rendering SVG axes. The summary above
    // can be ready before that layout pass, especially on a CI runner.
    await chart.locator("svg text").first().waitFor({ state: "visible" });
    const circle = chart.locator("circle");
    await circle.waitFor({ state: "visible" });
    const plotWidth = await chart
      .locator("svg")
      .first()
      .evaluate((svg) => svg.getBoundingClientRect().width - 60);
    assert.ok(
      Number(await circle.getAttribute("cx")) > plotWidth * 0.85,
      "A point two minutes ago belongs near the end of the one-hour window",
    );
    chartMode = "fresh";
    state.components[0].metrics = [metric("cpu_usage", 0.25, "ratio")];
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await chart
      .getByTestId("current-metric")
      .filter({ hasText: "25.0%" })
      .waitFor();
    state.components[0].metrics = [metric("cpu_usage", 0.35, "ratio")];
    await page.evaluate(
      (s) =>
        window.testStream.dispatchEvent(
          new MessageEvent("snapshot", { data: JSON.stringify(s) }),
        ),
      { ...state, observed_at: at() },
    );
    await chart
      .getByTestId("current-metric")
      .filter({ hasText: "35.0%" })
      .waitFor();
    await page.evaluate(() => window.testStream.onerror());
    await chart
      .getByTestId("current-metric")
      .filter({ hasText: "Stale" })
      .waitFor();
    assert.doesNotMatch(
      await chart.locator(".section-heading").innerText(),
      /25.0%/,
    );
    chartMode = "gaps";
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    // Three runs: an explicitly unavailable sample and a missing interval must
    // each break the line rather than imply continuously observed values.
    await page.waitForFunction(() =>
      [
        ...document.querySelectorAll('.trend-section .chart path[fill="none"]'),
      ].some(
        (path) => (path.getAttribute("d")?.match(/M/g) || []).length === 3,
      ),
    );
    await choose(page, "History component", "N3");
    await page
      .getByRole("combobox", { name: "History metric", exact: true })
      .click();
    assert.deepEqual(await page.getByRole("option").allTextContents(), [
      "Downlink",
      "Uplink",
    ]);
    await page.keyboard.press("Escape");
    await choose(page, "History component", "OCUDU gNB");
    assert.match(
      await page
        .getByRole("combobox", { name: "History metric", exact: true })
        .innerText(),
      /CQI/,
    );
    await page.goto(base + "/gnb");
    await page
      .getByRole("heading", { name: "RF configuration", exact: true })
      .waitFor();
    assert.match(
      await page.getByRole("main").innerText(),
      /Sample rate \(MSps\)/,
    );
    assert.match(await page.getByRole("main").innerText(), /\/opt\/gnb_file/);
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
    "Information scope, stale chart values, units, single-point position, current sample, stream loss, metric ownership and RF labels passed on desktop/mobile",
  );
} finally {
  await browser.close();
}

async function choose(page, label, option) {
  await page.getByRole("combobox", { name: label, exact: true }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}
