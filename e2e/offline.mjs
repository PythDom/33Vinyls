// End-to-end check of the offline must-have, in Chromium emulating an Android phone.
// Usage: node e2e/offline.mjs http://localhost:8765 [screenshot-dir]
import { createRequire } from "node:module";
// works with a project install or the globally installed Playwright (NODE_PATH)
const { chromium, devices } = createRequire(import.meta.url)("playwright");
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";

const BASE = process.argv[2] ?? "http://localhost:8765";
const SHOTS = process.argv[3];
const browser = await chromium.launch();
const context = await browser.newContext({ ...devices["Pixel 7"] });
const page = await context.newPage();
const shot = async (name) => SHOTS && page.screenshot({ path: `${SHOTS}/${name}.png` });
const step = (s) => console.log("•", s);

step("register the first (admin) account");
await page.goto(BASE);
await page.getByLabel("Username").fill("dom");
await page.getByLabel("Password").fill("correct horse");
await page.getByRole("button", { name: "Create account" }).click();
await page.getByText("No records yet.").waitFor();

step("find a record on (demo) Discogs and check the price");
await page.getByRole("button", { name: /Find/ }).click();
await page.getByLabel("Artist, title…").fill("velvet static neon harbour");
await page.getByRole("button", { name: "Search", exact: true }).click();
await page.getByText("Harbourline HL 2001").first().click();
await page.getByText("Suggested for VG+").waitFor();
await page.getByLabel("Shop price in euro").fill("60");
await page.getByRole("button", { name: "Is it a deal?" }).click();
await page.getByText("Good deal").waitFor();
await shot("2-release-price");

step("which pressing? answer with the runout");
await page.getByRole("button", { name: "Which pressing?" }).click();
await page.getByPlaceholder("e.g. HL-2001-A2").fill("HL 2001 A2");
await page.getByRole("button", { name: "Compare" }).click();
await page.getByText(/Matched: runout/).first().waitFor();
await shot("3-pressing");
await page.getByText(/Matched: runout/).first().click();
await page.getByRole("button", { name: /Add to collection/ }).click();
await page.getByText("Saved on this phone").waitFor();

step("add 2,000 more records through the sync API (bulk test data)");
const releaseIds = [100101, 100103, 100104, 100105, 100106, 100201, 100202, 100203, 100204, 100301, 100302, 100303, 100401, 100402, 100501, 100502, 100601, 100701, 100702, 100801];
for (let batch = 0; batch < 4; batch++) {
  const ops = Array.from({ length: 500 }, (_, i) => {
    const n = batch * 500 + i;
    return { id: randomUUID(), release_id: releaseIds[n % releaseIds.length], kind: n % 10 === 0 ? "want" : "collection",
      fields: { media_grade: ["NM", "VG+", "VG"][n % 3], location: `Box ${1 + (n % 40)}`, notes: n === 777 ? "signed by the band" : "" },
      updated_at: new Date().toISOString() };
  });
  const r = await context.request.post(`${BASE}/api/sync`, { data: { ops } });
  assert.equal(r.status(), 200);
}
await page.goto(`${BASE}/#/settings`);
await page.getByRole("button", { name: "Sync now" }).click();
await page.getByText("✓ Offline ready — 2001 records, 21 covers").waitFor({ timeout: 90000 });
const offlineText = await page.getByText("✓ Offline ready").innerText();
console.log("  ", offlineText);
await shot("5-settings-offline-ready");

step("AIRPLANE MODE: go offline, close and reopen the app");
await context.setOffline(true);
await page.goto("about:blank");
await page.goto(`${BASE}/`);
// 1,801 in the collection + 200 on the wantlist, all read from the phone
await page.getByRole("tab", { name: "Collection 1801" }).waitFor({ timeout: 10000 });
await page.getByRole("tab", { name: "Wantlist 200" }).waitFor();
await page.getByText("Offline", { exact: true }).waitFor();
await shot("1-collection-offline");

step("search offline: artist, catalogue number, typo, notes, runout");
const search = page.getByLabel("Search your records");
const timed = async (q, expect) => {
  const t0 = Date.now();
  await search.fill(q);
  await page.getByText(expect).first().waitFor();
  const ms = Date.now() - t0;
  console.log(`   "${q}" → ${await page.locator(".summary").innerText()} in ${ms} ms`);
  return ms;
};
assert.ok((await timed("okafor", "Marisol Okafor — Tidal Rooms")) < 1500);
await timed("hl2001", "The Velvet Static — Neon Harbour");
await timed("satelites", "Kestrel Union — Paper Satellites");
await timed("signed", "1 record");
await timed("HL-2001-A2", "1 record");
await shot("4-search-offline");

step("browse offline: filter by decade and location, open a record with its cover");
await search.fill("");
await page.getByRole("button", { name: /Filters/ }).click();
await page.getByLabel("Decade").selectOption("1980s");
await page.getByLabel("Location").selectOption("Box 10");
const first = page.locator(".list .row").first();
await first.click();
await page.getByRole("heading", { level: 1 }).waitFor();
const coverSrc = await page.locator(".hero img.cover").getAttribute("src");
assert.ok(coverSrc?.startsWith("blob:"), `cover should come from the phone, got ${coverSrc}`);

step("edit a note offline");
await page.getByLabel("Notes").fill("checked offline");
await page.getByRole("button", { name: "Save" }).click();
await page.getByText("1 to sync").waitFor();

step("offline barcode check against my own records");
await page.getByRole("button", { name: /Scan/ }).click();
await page.getByLabel("Barcode digits").fill("4006381333931"); // a barcode not in the collection
await page.getByRole("button", { name: "Check" }).click();
await page.getByText("Not in your collection or wantlist.").waitFor();
const owned = "5054197012341";
await page.getByLabel("Barcode digits").fill(owned);
await page.getByRole("button", { name: "Check" }).click();
await page.getByText("You own this").first().waitFor();

step("back online: the offline edit syncs to the server");
await context.setOffline(false);
await page.evaluate(() => window.dispatchEvent(new Event("online")));
await page.getByText("Synced", { exact: true }).waitFor({ timeout: 30000 });
const pulled = await (await context.request.get(`${BASE}/api/sync?since=0`)).json();
assert.ok(pulled.items.some((i) => i.fields.notes === "checked offline"), "edit reached the server");

console.log("\nALL OFFLINE ACCEPTANCE CHECKS PASSED");
await browser.close();
