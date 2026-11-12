import { describe, expect, it } from "vitest";
import { applyFilters, buildIndex, buildRows, facetValues, matchBarcode, searchRows, sortRows } from "./search";
import type { LocalItem, Release } from "./types";

const rel = (id: number, artist: string, title: string, extra: Partial<Release> = {}): Release => ({
  id, master_id: null, artist, title, year: 1972, country: "UK", labels: [{ name: "Harbourline", catno: "HL 2001" }],
  formats: ["Vinyl, LP, Album"], barcodes: [], matrix: [], genres: ["Rock"], styles: [], tracklist: [], notes: "",
  image: "", discogs_url: "", ...extra,
});
const item = (id: string, release_id: number, fields = {}, kind: "collection" | "want" = "collection"): LocalItem => ({
  id, release_id, kind, fields, updated_at: "2026-11-12T00:00:00Z", deleted: 0, dirty: 0,
});

const releases = new Map<number, Release>([
  [1, rel(1, "The Velvet Static", "Neon Harbour", { matrix: ["HL-2001-A1"] })],
  [2, rel(2, "Marisol Okafor", "Tidal Rooms", { year: 1979, country: "France", labels: [{ name: "Disques Marée", catno: "DM 33.112" }], genres: ["Jazz"] })],
  [3, rel(3, "Kestrel Union", "Paper Satellites", { year: 1985, barcodes: ["5012345678900"], formats: ['Vinyl, 7", Single'] })],
]);
const rows = buildRows(
  [item("a", 1, { location: "Shelf 2", media_grade: "VG+" }), item("b", 2, { notes: "signed copy" }), item("c", 3), item("d", 2, {}, "want"), { ...item("e", 1), deleted: 1 }],
  releases,
  new Map(),
);
const index = buildIndex(rows);
const ids = (r: typeof rows) => r.map((x) => x.item.id);

describe("offline search", () => {
  it("skips deleted items", () => expect(ids(rows)).not.toContain("e"));
  it("finds by artist prefix", () => expect(ids(searchRows(rows, index, "velv"))).toEqual(["a"]));
  it("ignores accents", () => expect(ids(searchRows(rows, index, "maree"))).toEqual(expect.arrayContaining(["b", "d"])));
  it("tolerates a typo", () => expect(ids(searchRows(rows, index, "satelites"))).toEqual(["c"]));
  it("finds catalogue numbers typed compactly", () => expect(ids(searchRows(rows, index, "hl2001"))).toContain("a"));
  it("finds runout text", () => expect(ids(searchRows(rows, index, "HL-2001-A1"))).toEqual(["a"]));
  it("finds notes and storage location", () => {
    expect(ids(searchRows(rows, index, "signed"))).toEqual(["b"]);
    expect(ids(searchRows(rows, index, "shelf 2"))).toEqual(["a"]);
  });
  it("matches a barcode exactly", () => expect(ids(searchRows(rows, index, "5012345678900"))).toEqual(["c"]));
});

describe("browse", () => {
  it("filters by kind and decade", () => {
    expect(ids(applyFilters(rows, { kind: "collection", decade: "1970s" }))).toEqual(["a", "b"]);
    expect(ids(applyFilters(rows, { kind: "want" }))).toEqual(["d"]);
  });
  it("filters by format", () => expect(ids(applyFilters(rows, { kind: "collection", format: '7"' }))).toEqual(["c"]));
  it("sorts by year", () => expect(ids(sortRows(applyFilters(rows, { kind: "collection" }), "year"))).toEqual(["a", "b", "c"]));
  it("lists facet values", () => expect(facetValues(rows, "collection").country).toEqual(["France", "UK"]));
  it("checks barcodes for the scanner", () => {
    expect(ids(matchBarcode(rows, "5012345678900"))).toEqual(["c"]);
    expect(ids(matchBarcode(rows, "0000000000000"))).toEqual([]);
  });
});
