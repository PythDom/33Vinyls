/** Offline search, filtering and sorting of the local collection. Runs entirely on the phone. */
import MiniSearch from "minisearch";
import type { Kind, LocalItem, PriceCard, Release } from "./types";

export interface Row {
  item: LocalItem;
  release: Release;
  value: number | null;
}

export function fold(text: string): string {
  return text.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

const compact = (s: string) => fold(s).replace(/[^a-z0-9]/g, "");

export function formatKind(r: Release): string {
  const f = (r.formats[0] || "").toLowerCase();
  if (f.includes('7"')) return '7"';
  if (f.includes('10"')) return '10"';
  if (f.includes('12"')) return '12"';
  if (/^[2-9]×/.test(r.formats[0] || "")) return (r.formats[0] || "").split(",")[0];
  if (f.includes("lp")) return "LP";
  return (r.formats[0] || "Other").split(",")[0];
}

export function decade(year: number | null): string {
  return year ? `${Math.floor(year / 10) * 10}s` : "Unknown";
}

export function itemValue(item: LocalItem, price?: PriceCard): number | null {
  if (!price) return null;
  const g = item.fields.media_grade;
  return (g && price.suggested?.[g]) || price.median || price.lowest || null;
}

export function buildRows(items: LocalItem[], releases: Map<number, Release>, prices: Map<number, PriceCard>): Row[] {
  const rows: Row[] = [];
  for (const item of items) {
    if (item.deleted) continue;
    const release = releases.get(item.release_id);
    if (!release) continue;
    rows.push({ item, release, value: itemValue(item, prices.get(item.release_id)) });
  }
  return rows;
}

export function buildIndex(rows: Row[]): MiniSearch {
  const index = new MiniSearch({
    idField: "id",
    fields: ["artist", "title", "label", "catno", "codes", "notes", "location", "genre", "place", "format", "tracks"],
    processTerm: (term) => fold(term),
    searchOptions: {
      prefix: true,
      fuzzy: (term) => (term.length > 3 ? 0.2 : false),
      combineWith: "AND",
      boost: { artist: 3, title: 3, catno: 2, codes: 2 },
    },
  });
  index.addAll(
    rows.map(({ item, release: r }) => ({
      id: item.id,
      artist: r.artist,
      title: r.title,
      label: r.labels.map((l) => l.name).join(" "),
      // catalogue numbers both as typed ("HL 2001") and compact ("hl2001")
      catno: r.labels.map((l) => `${l.catno} ${compact(l.catno)}`).join(" "),
      codes: [...r.barcodes, ...r.matrix, ...r.matrix.map(compact)].join(" "),
      notes: item.fields.notes || "",
      location: item.fields.location || "",
      genre: [...r.genres, ...r.styles].join(" "),
      place: `${r.country} ${r.year ?? ""} ${item.fields.purchase_place || ""}`,
      format: r.formats.join(" "),
      tracks: r.tracklist.map((t) => t.title).join(" "),
    })),
  );
  return index;
}

export interface Filters {
  kind: Kind;
  decade?: string;
  country?: string;
  format?: string;
  grade?: string;
  location?: string;
  label?: string;
  genre?: string;
}

export type SortKey = "artist" | "title" | "year" | "added" | "value";

export function applyFilters(rows: Row[], f: Filters): Row[] {
  return rows.filter(({ item, release: r }) => {
    if (item.kind !== f.kind) return false;
    if (f.decade && decade(r.year) !== f.decade) return false;
    if (f.country && r.country !== f.country) return false;
    if (f.format && formatKind(r) !== f.format) return false;
    if (f.grade && (item.fields.media_grade || "") !== f.grade) return false;
    if (f.location && (item.fields.location || "") !== f.location) return false;
    if (f.label && !r.labels.some((l) => l.name === f.label)) return false;
    if (f.genre && !r.genres.includes(f.genre)) return false;
    return true;
  });
}

const byText = (a: string, b: string) => fold(a).localeCompare(fold(b));

export function sortRows(rows: Row[], key: SortKey): Row[] {
  const sorted = [...rows];
  sorted.sort((a, b) => {
    switch (key) {
      case "title":
        return byText(a.release.title, b.release.title);
      case "year":
        return (a.release.year ?? 9999) - (b.release.year ?? 9999) || byText(a.release.artist, b.release.artist);
      case "added":
        return (b.item.fields.added_at || b.item.updated_at).localeCompare(a.item.fields.added_at || a.item.updated_at);
      case "value":
        return (b.value ?? -1) - (a.value ?? -1);
      default:
        return byText(a.release.artist, b.release.artist) || (a.release.year ?? 0) - (b.release.year ?? 0);
    }
  });
  return sorted;
}

export function searchRows(rows: Row[], index: MiniSearch | null, query: string): Row[] {
  const q = query.trim();
  if (!q || !index) return rows;
  const byId = new Map(rows.map((r) => [r.item.id, r]));
  const digits = q.replace(/\D/g, "");
  if (digits.length >= 8 && digits.length === q.replace(/\s/g, "").length) {
    // a barcode typed or scanned: exact match
    return rows.filter((r) => r.release.barcodes.some((b) => b === digits || b.endsWith(digits) || digits.endsWith(b)));
  }
  return index
    .search(q)
    .map((hit) => byId.get(hit.id as string))
    .filter((r): r is Row => !!r);
}

export function facetValues(rows: Row[], kind: Kind) {
  const pick = (fn: (r: Row) => string | string[] | undefined) => {
    const set = new Set<string>();
    for (const row of rows) {
      if (row.item.kind !== kind) continue;
      const v = fn(row);
      for (const x of Array.isArray(v) ? v : [v]) if (x) set.add(x);
    }
    return [...set].sort((a, b) => fold(a).localeCompare(fold(b)));
  };
  return {
    decade: pick((r) => decade(r.release.year)),
    country: pick((r) => r.release.country),
    format: pick((r) => formatKind(r.release)),
    grade: pick((r) => r.item.fields.media_grade),
    location: pick((r) => r.item.fields.location),
    label: pick((r) => r.release.labels.map((l) => l.name)),
    genre: pick((r) => r.release.genres),
  };
}

/** Local barcode check used by the scanner, works offline. */
export function matchBarcode(rows: Row[], code: string): Row[] {
  const digits = code.replace(/\D/g, "");
  const variants = new Set([digits, digits.replace(/^0/, ""), "0" + digits]);
  return rows.filter((r) => r.release.barcodes.some((b) => variants.has(b)));
}
