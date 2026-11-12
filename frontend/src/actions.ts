/** Local writes. Everything is saved on the phone first, then synced in the background. */
import { apiBlob } from "./api";
import { db, nowIso, uuid } from "./db";
import { scheduleSync } from "./sync";
import type { ItemFields, Kind, LocalItem, PriceCard, Release } from "./types";

export async function addRelease(release: Release, kind: Kind, fields: ItemFields = {}, price?: PriceCard | null): Promise<string> {
  const d = db();
  const { owned: _owned, ...clean } = release;
  void _owned;
  const item: LocalItem = {
    id: uuid(),
    release_id: release.id,
    kind,
    fields: { added_at: nowIso(), ...fields },
    updated_at: nowIso(),
    deleted: 0,
    dirty: 1,
  };
  await d.transaction("rw", d.items, d.releases, d.prices, async () => {
    await d.releases.put(clean);
    if (price) await d.prices.put(price);
    await d.items.put(item);
  });
  if (!(await d.thumbs.get(release.id))) {
    const blob = await apiBlob(`/api/thumbs/${release.id}`);
    if (blob) await d.thumbs.put({ id: release.id, blob });
  }
  scheduleSync();
  return item.id;
}

export async function updateItem(id: string, patch: { fields?: ItemFields; kind?: Kind }) {
  const d = db();
  const item = await d.items.get(id);
  if (!item) return;
  await d.items.put({
    ...item,
    kind: patch.kind ?? item.kind,
    fields: { ...item.fields, ...(patch.fields ?? {}) },
    updated_at: nowIso(),
    dirty: 1,
  });
  scheduleSync();
}

export async function removeItem(id: string) {
  const d = db();
  const item = await d.items.get(id);
  if (!item) return;
  await d.items.put({ ...item, deleted: 1, updated_at: nowIso(), dirty: 1 });
  scheduleSync();
}
