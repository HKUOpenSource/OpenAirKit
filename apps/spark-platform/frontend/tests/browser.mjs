import { chromium } from "playwright";
import fs from "node:fs/promises";
import assert from "node:assert/strict";

const base = process.env.AOC_TEST_URL || "http://127.0.0.1:8877";
const password = process.env.AOC_TEST_PASSWORD;
if (!password) throw new Error("AOC_TEST_PASSWORD is required");
await fs.mkdir("../../../artifacts/monitor-browser", { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 390, height: 844 },
  ]) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.addInitScript(() => {
      window.EventSource = class extends EventTarget {
        constructor() {
          super();
          window.testStream = this;
        }
        close() {}
      };
    });
    await page.goto(base);
    await page.getByLabel("Administrator password").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page
      .getByRole("heading", { name: "Overview", exact: true })
      .waitFor();
    for (const name of [
      "gNB",
      "Core Network",
      "Devices",
      "Events",
      "Overview",
    ]) {
      if (viewport.width <= 760)
        await page
          .getByRole("button", { name: "Open navigation", exact: true })
          .click();
      await primaryNavigation(page, viewport.width)
        .getByRole("link", { name, exact: true })
        .click();
      if (viewport.width <= 760)
        await page
          .getByRole("dialog", { name: "Navigation", exact: true })
          .waitFor({ state: "hidden" });
      await page
        .getByRole("heading", { name, exact: true, level: 1 })
        .waitFor();
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
      assert.equal(
        /\p{Script=Han}/u.test(await page.locator("body").innerText()),
        false,
      );
    }
    const body = await page.locator("body").innerText();
    assert.doesNotMatch(
      body,
      /Legacy OAI|Switch radio stack|Data \/ IMS sessions/,
    );
    assert.equal(await page.locator('nav a[href="/ims"]').count(), 0);
    assert.equal(
      await page
        .locator("button")
        .filter({ hasText: /Switch radio stack/ })
        .count(),
      0,
    );
    if (viewport.width <= 760)
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
    assert.deepEqual(
      await primaryNavigation(page, viewport.width)
        .getByRole("link")
        .allTextContents(),
      ["Overview", "gNB", "Core Network", "Devices", "Events"],
    );
    if (viewport.width <= 760) {
      await page.keyboard.press("Escape");
      await page
        .getByRole("dialog", { name: "Navigation", exact: true })
        .waitFor({ state: "hidden" });
    }
    assert.equal(await page.locator(".spark-topology-node").count(), 7);
    await page.screenshot({
      path: `../../../artifacts/monitor-browser/spark-${viewport.width}.png`,
      fullPage: true,
    });

    await page.goto(base + "/devices");
    const deviceLinks = page.locator("table a");
    if (await deviceLinks.count()) {
      await deviceLinks.first().click();
      await page
        .getByRole("heading", { name: "PDU sessions", exact: true })
        .waitFor();
      const detailUrl = page.url();
      await page.reload();
      await page
        .getByRole("heading", { name: "PDU sessions", exact: true })
        .waitFor();
      assert.equal(page.url(), detailUrl);
      await page.getByRole("link", { name: "Devices", exact: true }).click();
      await page.getByLabel("Search devices").fill("no-such-device");
      await page.getByText("No device evidence", { exact: true }).waitFor();
    }

    await page.goto(base + "/core");
    const componentLinks = page.locator('table a[href^="/components/"]');
    if (await componentLinks.count()) {
      await componentLinks.first().click();
      await page
        .getByRole("heading", { name: "Current metrics", exact: true })
        .waitFor();
      const detailUrl = page.url();
      await page.reload();
      await page
        .getByRole("heading", { name: "Current metrics", exact: true })
        .waitFor();
      assert.equal(page.url(), detailUrl);
      await page
        .getByRole("link", { name: "Core Network", exact: true })
        .click();
    }

    await page.goto(base + "/operations");
    await page.getByRole("button", { name: "Start", exact: true }).click();
    await page
      .getByRole("alertdialog", { name: "Confirm stack operation" })
      .waitFor();
    await page.getByRole("button", { name: "Back", exact: true }).click();
    assert.equal(
      await page
        .getByRole("alertdialog", { name: "Confirm stack operation" })
        .count(),
      0,
    );
    await page.waitForFunction(() =>
      document.querySelector(".collection-status .badge.ok"),
    );
    await page.evaluate(() => window.testStream.onerror());
    await page.waitForFunction(() =>
      document.querySelector(".collection-status .badge.stale"),
    );
    await page.reload();
    await page.waitForFunction(() =>
      document.querySelector(".collection-status .badge.ok"),
    );
    const fresh = {
      schema_version: 4,
      observed_at: await page.evaluate(() => new Date().toISOString()),
      collector_status: "ok",
      active_stack: "ocudu",
      observations: [],
      services: [],
      devices: [],
      events: [],
    };
    await page.evaluate(
      (snapshot) =>
        window.testStream.dispatchEvent(
          new MessageEvent("snapshot", { data: JSON.stringify(snapshot) }),
        ),
      fresh,
    );
    await page.evaluate(() =>
      window.testStream.dispatchEvent(new Event("auth_expired")),
    );
    await page.getByLabel("Administrator password").waitFor();
    await page.getByLabel("Administrator password").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("button", { name: "Account", exact: true }).click();
    await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
    await page.getByLabel("Administrator password").waitFor();
    assert.deepEqual(errors, []);
    await page.close();
  }
  console.log(
    "Single-stack navigation, details, English UI, responsive layout, stream loss, auth expiry and sign out passed",
  );
} finally {
  await browser.close();
}

function primaryNavigation(page, width) {
  return width <= 760
    ? page.getByRole("dialog", { name: "Navigation", exact: true })
    : page.getByRole("navigation", { name: "Primary navigation", exact: true });
}
