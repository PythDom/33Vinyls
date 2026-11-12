import { useMemo, useState } from "react";
import { Cover, eur } from "../components";
import { db } from "../db";
import { go, useLive } from "../hooks";
import { applyFilters, buildIndex, buildRows, facetValues, searchRows, sortRows, type Filters, type SortKey } from "../search";
import type { Kind } from "../types";

const PAGE = 150;
const FILTER_LABELS: Record<string, string> = {
  decade: "Decade", country: "Country", format: "Format", grade: "Grade", location: "Location", label: "Label", genre: "Genre",
};

export default function Collection() {
  const items = useLive(() => db().items.toArray(), [], []);
  const releases = useLive(async () => new Map((await db().releases.toArray()).map((r) => [r.id, r])), [], new Map());
  const prices = useLive(async () => new Map((await db().prices.toArray()).map((p) => [p.release_id, p])), [], new Map());
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<Filters>({ kind: "collection" });
  const [sort, setSort] = useState<SortKey>("artist");
  const [showFilters, setShowFilters] = useState(false);
  const [limit, setLimit] = useState(PAGE);

  const rows = useMemo(() => buildRows(items, releases, prices), [items, releases, prices]);
  const index = useMemo(() => buildIndex(rows), [rows]);
  const facets = useMemo(() => facetValues(rows, filters.kind), [rows, filters.kind]);
  const counts = useMemo(() => ({
    collection: rows.filter((r) => r.item.kind === "collection").length,
    want: rows.filter((r) => r.item.kind === "want").length,
  }), [rows]);
  const visible = useMemo(() => {
    const filtered = applyFilters(searchRows(rows, index, query), filters);
    return query.trim() ? filtered : sortRows(filtered, sort);
  }, [rows, index, query, filters, sort]);
  const total = useMemo(() => visible.reduce((s, r) => s + (r.value ?? 0), 0), [visible]);
  const money = useMemo(() => {
    const coll = rows.filter((r) => r.item.kind === "collection");
    const valued = coll.filter((r) => r.value != null);
    const paid = coll.reduce((s, r) => s + (r.item.fields.purchase_price ?? 0), 0);
    const both = coll.filter((r) => r.value != null && r.item.fields.purchase_price != null);
    return {
      value: valued.reduce((s, r) => s + (r.value ?? 0), 0),
      valued: valued.length,
      count: coll.length,
      paid,
      gain: both.reduce((s, r) => s + (r.value ?? 0) - (r.item.fields.purchase_price ?? 0), 0),
      hasPaid: both.length > 0,
    };
  }, [rows]);
  const activeFilters = Object.entries(filters).filter(([k, v]) => k !== "kind" && v).length;

  const setKind = (kind: Kind) => {
    setFilters({ kind });
    setLimit(PAGE);
  };

  return (
    <main className="page">
      <div className="search-bar">
        <input
          type="search"
          placeholder="Search artist, title, label, cat#, barcode, runout, notes…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setLimit(PAGE);
          }}
          aria-label="Search your records"
        />
      </div>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={filters.kind === "collection"} onClick={() => setKind("collection")}>
          Collection <span className="count">{counts.collection}</span>
        </button>
        <button role="tab" aria-selected={filters.kind === "want"} onClick={() => setKind("want")}>
          Wantlist <span className="count">{counts.want}</span>
        </button>
      </div>
      <div className="toolbar">
        <button className={activeFilters ? "chip active" : "chip"} onClick={() => setShowFilters(!showFilters)}>
          Filters{activeFilters ? ` (${activeFilters})` : ""}
        </button>
        <label className="sort">
          <span className="muted small">Sort</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} disabled={!!query.trim()}>
            <option value="artist">Artist</option>
            <option value="title">Title</option>
            <option value="year">Year</option>
            <option value="added">Recently added</option>
            <option value="value">Value</option>
          </select>
        </label>
      </div>
      {showFilters && (
        <div className="filters">
          {(Object.keys(FILTER_LABELS) as (keyof typeof facets)[]).map((key) =>
            facets[key].length ? (
              <label className="field" key={key}>
                <span>{FILTER_LABELS[key]}</span>
                <select value={(filters as unknown as Record<string, string>)[key] ?? ""} onChange={(e) => setFilters({ ...filters, [key]: e.target.value || undefined })}>
                  <option value="">All</option>
                  {facets[key].map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
            ) : null,
          )}
          {activeFilters > 0 && (
            <button className="link" onClick={() => setFilters({ kind: filters.kind })}>
              Clear filters
            </button>
          )}
        </div>
      )}
      {filters.kind === "collection" && !query.trim() && activeFilters === 0 && money.count > 0 && (
        <div className="stats" aria-label="Collection value">
          <div><span className="muted small">Est. value</span><strong>{eur(money.value)}</strong></div>
          <div><span className="muted small">Paid</span><strong>{money.hasPaid ? eur(money.paid) : "—"}</strong></div>
          <div><span className="muted small">Gain</span><strong className={money.gain >= 0 ? "gain-pos" : "gain-neg"}>{money.hasPaid ? eur(money.gain) : "—"}</strong></div>
        </div>
      )}
      {filters.kind === "collection" && money.count > 0 && money.valued < money.count && !query.trim() && activeFilters === 0 && (
        <p className="muted small">{money.count - money.valued} records have no price yet: prices are filled in automatically in the background.</p>
      )}
      <p className="muted small summary">
        {visible.length} record{visible.length === 1 ? "" : "s"}
        {filters.kind === "collection" && total > 0 ? ` · est. ${eur(total)}` : ""}
      </p>
      {rows.length === 0 ? (
        <div className="empty">
          <p>No records yet.</p>
          <button className="primary" onClick={() => go("/scan")}>
            Scan your first record
          </button>
        </div>
      ) : (
        <ul className="list">
          {visible.slice(0, limit).map(({ item, release: r, value }) => (
            <li key={item.id}>
              <button className="row" onClick={() => go(`/item/${item.id}`)}>
                <Cover id={r.id} />
                <span className="row-text">
                  <strong>{r.artist} — {r.title}</strong>
                  <span className="muted small">{[r.year, r.country, r.labels[0] && `${r.labels[0].name} ${r.labels[0].catno}`].filter(Boolean).join(" · ")}</span>
                  <span className="small">
                    {item.fields.media_grade && <span className="tag">{item.fields.media_grade}</span>}
                    {item.fields.location && <span className="tag">{item.fields.location}</span>}
                    {item.dirty ? <span className="tag pending">not synced</span> : null}
                  </span>
                </span>
                {value != null && <span className="value">{eur(value)}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {visible.length > limit && (
        <button className="secondary wide" onClick={() => setLimit(limit + PAGE)}>
          Show more ({visible.length - limit} left)
        </button>
      )}
    </main>
  );
}
