import { chromium } from "playwright";
import fs from "node:fs/promises";

const base = process.argv[2] || "http://127.0.0.1:8880";
const output = new URL("../../../local/jetson-v2-browser/", import.meta.url).pathname;
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const failures = [];

try {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    page.on("pageerror", error => failures.push(`${viewport.width}: ${error.message}`));
    await page.goto(base);
    await page.getByLabel("Password", { exact: true }).fill("Jetson-Local-Preview-2026");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("heading", { name: "Network overview", exact: true, level: 1 }).waitFor();
    for (const [path, label, heading] of [["/", "Overview", "Network overview"], ["/setup", "Device Setup", "Device Setup"], ["/speed", "Speed Test", "Speed Test"], ["/history", "History", "History"], ["/settings", "Settings", "Settings"]]) {
      await page.goto(base + path);
      await page.getByRole("heading", { name: heading, exact: true, level: 1 }).waitFor();
      await page.screenshot({ path: `${output}${viewport.width}-${label.toLowerCase().replaceAll(" ", "-")}.png`, fullPage: true });
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) failures.push(`${viewport.width} ${label}: horizontal overflow`);
    }
    if (viewport.width === 1440) {
      await page.goto(base + "/setup");
      await page.getByRole("button", { name: "Manual", exact: true }).click();
      await page.getByRole("button", { name: "Create setup plan", exact: true }).click();
      await page.getByRole("button", { name: "Confirm", exact: true }).click();
      await page.getByRole("button", { name: "Confirm and run", exact: true }).click();
      await page.getByRole("button", { name: "Run next step", exact: true }).waitFor();
      await page.reload();
      await page.getByRole("button", { name: "Run next step", exact: true }).waitFor();
      await page.getByRole("button", { name: "Cancel", exact: true }).click();
      await page.getByText("cancelled", { exact: true }).first().waitFor();
      await page.goto(base + "/speed");
      await page.getByRole("button", { name: "GO", exact: true }).click();
      await page.getByRole("button", { name: "Confirm", exact: true }).click();
      const currentResult = page.locator(".speed-result");
      await currentResult.getByText("38.0", { exact: true }).waitFor({ timeout: 10000 });
      await currentResult.getByText("8.0", { exact: true }).waitFor();
      await page.screenshot({ path: output + "speed-complete.png", fullPage: true });
      const denied = await page.evaluate(async () => (await fetch("/api/v1/maintenance", { method: "POST", headers: { "Content-Type": "application/json" }, body: '{"enabled":true}' })).status);
      if (denied !== 403) failures.push("Write without CSRF was accepted");
      await page.route("**/api/v1/events/stream", route => route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: unavailable\ndata: {}\n\n" }));
      await page.goto(base + "/");
      await page.getByText("Live stream unavailable. Current values are marked stale until new evidence arrives.").waitFor({ timeout: 15000 });
      if (await page.getByText("5G data connection verified", { exact: true }).count()) failures.push("Stream loss retained a current connected claim");
      await page.screenshot({ path: output + "stream-stale.png", fullPage: true });
    } else {
      await page.getByRole("button", { name: "Open navigation", exact: true }).click();
      await page.getByRole("link", { name: "Speed Test", exact: true }).click();
      if (await page.locator("aside").evaluate(element => element.classList.contains("open"))) failures.push("Mobile drawer remained open");
    }
    await context.close();
  }
} finally {
  await browser.close();
}
console.log(JSON.stringify({ failures, output }));
if (failures.length) process.exit(1);
