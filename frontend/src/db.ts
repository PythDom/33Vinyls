/** The phone's local copy of the user's collection (IndexedDB). One database per user. */
import Dexie, { type Table } from "dexie";
import type { LocalItem, PriceCard, Release, User } from "./types";

export interface Thumb {
  id: number;
  blob: Blob;
}

export interface Meta {
  key: string;
  value: unknown;
}

export class LocalDB extends Dexie {
  items!: Table<LocalItem, string>;
  releases!: Table<Release, number>;
  prices!: Table<PriceCard, number>;
  thumbs!: Table<Thumb, number>;
  meta!: Table<Meta, string>;

  constructor(name: string) {
    super(name);
    this.version(1).stores({
      items: "id, release_id, kind, dirty, deleted",
      releases: "id, master_id",
      prices: "release_id",
      thumbs: "id",
      meta: "key",
    });
  }

  async getMeta<T>(key: string, fallback: T): Promise<T> {
    const row = await this.meta.get(key);
    return row ? (row.value as T) : fallback;
  }

  setMeta(key: string, value: unknown) {
    return this.meta.put({ key, value });
  }
}

const USER_KEY = "v33.user";
let current: LocalDB | null = null;

export function savedUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function rememberUser(user: User | null) {
  try {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
    else localStorage.removeItem(USER_KEY);
  } catch {
    /* storage blocked: the app still works for this visit */
  }
}

export function openDB(user: User): LocalDB {
  const name = `v33-u${user.id}`;
  if (!current || current.name !== name) {
    current?.close();
    current = new LocalDB(name);
  }
  return current;
}

export function db(): LocalDB {
  if (!current) throw new Error("Local database not open");
  return current;
}

export function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export function nowIso(): string {
  return new Date().toISOString();
}
