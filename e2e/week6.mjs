// End-to-end check of week 6: Discogs import, backups, sharing between two users, offline imported records.
// Usage: node e2e/week6.mjs http://localhost:8765   (fresh server, DISCOGS_MODE=demo, Sync folder mounted)
import { createRequire } from "node:module";
import assert from "node:assert/strict";
const { chromium, devices } = createRequire(import.meta.url)("playwright");

const BASE = process.argv[2] ?? "http://localhost:8765";
const SHOTS = process.argv[3];
const browser = await chromium.launch();
const step = (s) => console.log("•", s);

const dom = await browser.newContext({ ...devices["Pixel 7"] });
const page = await dom.newPage();
page.on("dialog", (d) => d.accept());

step("admin signs up and imports the (demo) Discogs collection");
await page.goto(BASE);
await page.getByLabel("Username").fill("dom");
await page.getByLabel("Password").fill("correct horse");
await page.getByRole("button", { name: "Create account" }).click();
await page.getByText("No records yet.").waitFor();
await page.goto(`${BASE}/#/settings`);
await page.getByRole("button", { name: "Import collection & wantlist" }).click();
await page.getByText(/Import finished: 11 added/).waitFor({ timeout: 30000 });
await page.getByRole("button", { name: /Records/ }).click();
await page.getByRole("tab", { name: "Collection 8" }).waitFor({ timeout: 20000 });
await page.getByRole("tab", { name: "Wantlist 3" }).waitFor();
await page.getByLabel("Search your records").fill("brussels");
await page.getByText("Juniper Vance").waitFor({ state: "detached" }).catch(() => {});
await page.getByText("1 record").waitFor();
if (SHOTS) await page.screenshot({ path: `${SHOTS}/w6-collection.png` });

step("backup: export now from Settings");
await page.goto(`${BASE}/#/settings`);
await page.getByRole("button", { name: "Export now" }).click();
await page.getByText(/Exported 33vinyls-/).waitFor({ timeout: 30000 });
if (SHOTS) await page.screenshot({ path: `${SHOTS}/w6-settings.png`, fullPage: true });

step("CSV download");
const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Collection (.csv)" }).click()]);
assert.match(download.suggestedFilename(), /^33vinyls-dom-collection-.*\.csv$/);

step("invite a friend, who signs up with the link");
const invite = await (await dom.request.post(`${BASE}/api/invites`)).json();
const alexCtx = await browser.newContext({ ...devices["Pixel 7"] });
const alex = await alexCtx.newPage();
await alex.goto(`${BASE}/#/login?invite=${invite.code}`);
await alex.getByLabel("Username").fill("alex");
await alex.getByLabel("Password").fill("password123");
await alex.getByRole("button", { name: "Create account" }).click();
await alex.getByText("No records yet.").waitFor();

step("alex adds a record dom wants, and shares the collection");
await alex.goto(`${BASE}/#/release/100101`);
await Promise.all([
  alex.waitForResponse((r) => r.url().endsWith("/api/sync") && r.request().method() === "POST"), // pushed ~1.5 s after a change
  alex.getByRole("button", { name: /Add to collection/ }).click(),
]);
await alex.getByText("Saved on this phone").waitFor();
await alex.goto(`${BASE}/#/settings`);
await Promise.all([alex.waitForResponse((r) => r.url().endsWith("/api/sharing") && r.request().method() === "PUT"), alex.getByLabel("Share my collection").check()]);

step("dom sees nothing until dom shares too (mutual)");
await page.goto(`${BASE}/#/release/100101`);
await page.getByRole("heading", { name: "Neon Harbour" }).waitFor();
assert.equal(await page.getByText("alex has this").count(), 0);
await page.goto(`${BASE}/#/settings`);
await Promise.all([page.waitForResponse((r) => r.url().endsWith("/api/sharing") && r.request().method() === "PUT"), page.getByLabel("Share my wantlist").check()]);
await page.goto(`${BASE}/#/release/100101`);
await page.getByText("alex has this").waitFor();
await page.goto(`${BASE}/#/friends`);
await page.getByRole("button", { name: "Collection (1)" }).click();
await page.getByText("On your wantlist").waitFor();

step("offline: imported records still searchable");
await dom.setOffline(true);
await page.goto("about:blank");
await page.goto(`${BASE}/`);
await page.getByRole("tab", { name: "Collection 8" }).waitFor({ timeout: 10000 });
await page.getByLabel("Search your records").fill("okafor");
await page.getByText("Marisol Okafor — Tidal Rooms").first().waitFor();

console.log("\nALL WEEK-6 CHECKS PASSED");
await browser.close();
