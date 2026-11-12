/** Offline-first sync: push local changes, pull server changes, download all cover thumbnails. */
import { api, apiBlob, ApiError, OFFLINE } from "./api";
import { db } from "./db";
import type { LocalItem, PriceCard, Release } from "./types";

export interface SyncState {
  status: "idle" | "syncing" | "offline" | "error" | "signed-out";
  message: string;
  lastSync: string | null;
  pending: number;
  thumbsMissing: number;
  offlineReady: boolean;
}

type Listener = (s: SyncState) => void;

let state: SyncState = { status: "idle", message: "", lastSync: null, pending: 0, thumbsMissing: 0, offlineReady: false };
const listeners = new Set<Listener>();
let running: Promise<void> | null = null;
let again = false;
let debounce: ReturnType<typeof setTimeout> | null = null;

function set(patch: Partial<SyncState>) {
  state = { ...state, ...patch };
  listeners.forEach((l) => l(state));
}

export function getSyncState() {
  return state;
}

export function subscribeSync(listener: Listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

interface PullResponse {
  cursor: number;
  generation: string;
  more: boolean;
  items: (Omit<LocalItem, "dirty" | "deleted"> & { deleted: boolean; seq: number })[];
  releases: Release[];
  prices: PriceCard[];
}

async function refreshCounts() {
  const d = db();
  const pending = await d.items.where("dirty").equals(1).count();
  const missing = await missingThumbs();
  const firstSync = await d.getMeta("firstSyncDone", false);
  const lastSync = await d.getMeta<string | null>("lastSync", null);
  set({ pending, thumbsMissing: missing.length, offlineReady: firstSync && missing.length === 0, lastSync });
}

async function missingThumbs(): Promise<number[]> {
  const d = db();
  const ids = new Set<number>();
  await d.items.each((i) => {
    if (!i.deleted) ids.add(i.release_id);
  });
  const have = new Set(await d.thumbs.toCollection().primaryKeys());
  return [...ids].filter((id) => !have.has(id));
}

async function push() {
  const d = db();
  for (;;) {
    const dirty = await d.items.where("dirty").equals(1).limit(200).toArray();
    if (!dirty.length) return;
    const ops = dirty.map((i) => ({ id: i.id, release_id: i.release_id, kind: i.kind, fields: i.fields, updated_at: i.updated_at, deleted: !!i.deleted }));
    const result = await api<{ applied: string[]; skipped: string[] }>("/api/sync", { method: "POST", json: { ops }, timeout: 30000 });
    const done = new Set([...result.applied, ...result.skipped]);
    await d.transaction("rw", d.items, async () => {
      for (const item of dirty) {
        if (!done.has(item.id)) continue;
        const fresh = await d.items.get(item.id);
        // only clear the flag if the item wasn't edited again while we were pushing
        if (fresh && fresh.updated_at === item.updated_at) await d.items.update(item.id, { dirty: 0 });
      }
    });
    if (done.size < dirty.length) return;
  }
}

async function pull() {
  const d = db();
  let cursor = await d.getMeta("cursor", 0);
  for (;;) {
    const data = await api<PullResponse>(`/api/sync?since=${cursor}`, { timeout: 30000 });
    const known = await d.getMeta<string | null>("generation", null);
    if (known && data.generation !== known && cursor !== 0) {
      // the server was restored from a backup: start again from scratch (unsynced edits are kept)
      await d.transaction("rw", [d.items, d.releases, d.prices, d.meta], async () => {
        await d.items.where("dirty").equals(0).delete();
        await d.releases.clear();
        await d.prices.clear();
        await d.setMeta("cursor", 0);
        await d.setMeta("generation", data.generation);
      });
      cursor = 0;
      continue;
    }
    if (known !== data.generation) await d.setMeta("generation", data.generation);
    await d.transaction("rw", [d.items, d.releases, d.prices, d.meta], async () => {
      if (data.releases.length) await d.releases.bulkPut(data.releases);
      if (data.prices.length) await d.prices.bulkPut(data.prices);
      for (const remote of data.items) {
        const local = await d.items.get(remote.id);
        if (local?.dirty && local.updated_at > remote.updated_at) continue; // our newer edit will be pushed
        await d.items.put({ id: remote.id, release_id: remote.release_id, kind: remote.kind, fields: remote.fields, updated_at: remote.updated_at, deleted: remote.deleted ? 1 : 0, dirty: 0 });
      }
      cursor = data.cursor;
      await d.setMeta("cursor", cursor);
    });
    if (!data.more) return;
  }
}

async function downloadThumbs() {
  const d = db();
  const missing = await missingThumbs();
  set({ thumbsMissing: missing.length });
  let failed = 0;
  const queue = [...missing];
  const worker = async () => {
    for (let id = queue.shift(); id !== undefined; id = queue.shift()) {
      const blob = await apiBlob(`/api/thumbs/${id}`);
      if (blob && blob.size > 0) await d.thumbs.put({ id, blob });
      else failed++;
      set({ thumbsMissing: Math.max(0, state.thumbsMissing - 1) });
    }
  };
  await Promise.all([worker(), worker(), worker(), worker()]);
  return failed;
}

async function run() {
  if (!navigator.onLine) {
    set({ status: "offline", message: "Offline: using the copy on this phone" });
    await refreshCounts();
    return;
  }
  set({ status: "syncing", message: "Syncing…" });
  try {
    await push();
    await pull();
    await db().setMeta("firstSyncDone", true);
    await downloadThumbs();
    await db().setMeta("lastSync", new Date().toISOString());
    set({ status: "idle", message: "" });
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) set({ status: "signed-out", message: "Sign in again to sync (your data on this phone is safe)." });
    else if (err instanceof ApiError && err.status === OFFLINE) set({ status: "offline", message: "Server not reachable: using the copy on this phone" });
    else set({ status: "error", message: err instanceof Error ? err.message : "Sync failed" });
  }
  await refreshCounts();
}

export function syncNow(): Promise<void> {
  if (running) {
    again = true;
    return running;
  }
  running = (async () => {
    do {
      again = false;
      await run();
    } while (again);
  })().finally(() => {
    running = null;
  });
  return running;
}

/** Called after every local edit: push soon, without blocking the UI. */
export function scheduleSync() {
  void refreshCounts();
  if (debounce) clearTimeout(debounce);
  debounce = setTimeout(() => void syncNow(), 1500);
}

let started = false;
export function startSync() {
  if (started) return;
  started = true;
  window.addEventListener("online", () => void syncNow());
  window.addEventListener("offline", () => set({ status: "offline", message: "Offline: using the copy on this phone" }));
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") void syncNow();
  });
  setInterval(() => void syncNow(), 5 * 60 * 1000);
  void refreshCounts().then(syncNow);
}

export function resetSyncState() {
  set({ status: "idle", message: "", lastSync: null, pending: 0, thumbsMissing: 0, offlineReady: false });
}

/** Ask Android/Chrome not to clear our storage when space is low. */
export async function requestPersistence(): Promise<boolean> {
  try {
    if (navigator.storage?.persisted && (await navigator.storage.persisted())) return true;
    return (await navigator.storage?.persist?.()) ?? false;
  } catch {
    return false;
  }
}
