import { chromium } from "playwright";
import fs from "node:fs/promises";

const base = process.argv[2] || "http://127.0.0.1:8880";
const output = new URL("../../../local/jetson-v2-browser/", import.meta.url)
  .pathname;
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const failures = [];

try {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    let streamRequests = 0;
    page.on("request", (request) => {
      if (new URL(request.url()).pathname === "/api/v1/events/stream") streamRequests++;
    });
    page.on("pageerror", (error) =>
      failures.push(`${viewport.width}: ${error.message}`),
    );
    await page.goto(base);
    await page
      .getByRole("textbox", { name: "Password Required", exact: true })
      .fill("Jetson-Local-Preview-2026");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page
      .getByRole("heading", { name: "Network overview", exact: true, level: 1 })
      .waitFor();
    if (viewport.width === 1440) {
      await page.getByText("5G data connection verified", { exact: true }).waitFor();
      // Cross two former 15-second stream lifetimes on one real HTTP connection.
      await page.waitForTimeout(35000);
      if (streamRequests !== 1) failures.push(`Periodic stream reconnects: ${streamRequests}`);
      if (await page.getByText(/Live stream unavailable|Device evidence is stale/).count())
        failures.push("Healthy live stream became stale");
    }
    for (const [path, label, heading] of [
      ["/", "Overview", "Network overview"],
      ["/setup", "Device Setup", "Device Setup"],
      ["/history", "History", "History"],
      ["/settings", "Settings", "Settings"],
    ]) {
      await page.goto(base + path);
      await page
        .getByRole("heading", { name: heading, exact: true, level: 1 })
        .waitFor();
      await page.screenshot({
        path: `${output}${viewport.width}-${label.toLowerCase().replaceAll(" ", "-")}.png`,
        fullPage: true,
      });
      if (
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        )
      )
        failures.push(`${viewport.width} ${label}: horizontal overflow`);
    }
    if (viewport.width === 1440) {
      await page.goto(base + "/setup");
      await page.getByRole("radio", { name: "Manual", exact: true }).click();
      await page
        .getByRole("button", { name: "Create setup plan", exact: true })
        .click();
      await page.getByRole("button", { name: "Confirm", exact: true }).click();
      await page
        .getByRole("button", { name: "Confirm and run", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Run next step", exact: true })
        .waitFor();
      await page.reload();
      await page
        .getByRole("button", { name: "Run next step", exact: true })
        .waitFor();
      await page.getByRole("button", { name: "Cancel", exact: true }).click();
      await page.getByText("cancelled", { exact: true }).first().waitFor();
      await page.goto(base + "/");
      await page.getByRole("button", { name: "Recover", exact: true }).click();
      await page.getByRole("button", { name: "Confirm", exact: true }).click();
      await page
        .locator(".job-panel .section-heading .badge.complete")
        .waitFor({ timeout: 15000 });
      if (await page.locator('a[href="/speed"]').count())
        failures.push("Retired navigation remains");
      const denied = await page.evaluate(
        async () =>
          (
            await fetch("/api/v1/maintenance", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: '{"enabled":true}',
            })
          ).status,
      );
      if (denied !== 403) failures.push("Write without CSRF was accepted");
      const connected = await page.evaluate(async () => (await fetch("/api/v1/status")).json());
      const staleStream = (route) => route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: `retry: 1000\n\nevent: status\ndata: ${JSON.stringify({
          ...connected, evidence_at: Date.now() / 1000 - 30,
        })}\n\n`,
      });
      await page.route("**/api/v1/events/stream", staleStream);
      await page.goto(base + "/");
      await page.getByText("Device evidence is stale. Waiting for a fresh device sample.")
        .waitFor();
      if (await page.getByText("5G data connection verified", { exact: true }).count())
        failures.push("Live transport retained a stale connected claim");
      if (await page.getByText("Live stream unavailable. Current values are marked stale until new evidence arrives.").count())
        failures.push("Stale device evidence was mislabeled as stream loss");
      await page.unroute("**/api/v1/events/stream", staleStream);
      await page.route("**/api/v1/events/stream", (route) =>
        route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: "event: unavailable\ndata: {}\n\n",
        }),
      );
      await page.goto(base + "/");
      await page
        .getByText(
          "Live stream unavailable. Current values are marked stale until new evidence arrives.",
        )
        .waitFor({ timeout: 15000 });
      if (
        await page
          .getByText("5G data connection verified", { exact: true })
          .count()
      )
        failures.push("Stream loss retained a current connected claim");
      await page.screenshot({
        path: output + "stream-stale.png",
        fullPage: true,
      });
    } else {
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
      await page.getByRole("link", { name: "History", exact: true }).click();
      await page
        .getByRole("dialog", { name: "Navigation", exact: true })
        .waitFor({ state: "hidden" });
    }
    await page.route("**/api/v1/jobs", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: '{"detail":"Session expired"}',
      }),
    );
    await page
      .getByRole("button", { name: "Sign in", exact: true })
      .waitFor({ timeout: 10000 });
    await context.close();
  }
} finally {
  await browser.close();
}
console.log(JSON.stringify({ failures, output }));
if (failures.length) process.exit(1);
