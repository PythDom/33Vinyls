import { useEffect, useState } from "react";
import { removeItem, updateItem } from "../actions";
import { Cover, eur, GradeSelect, PriceView, Section } from "../components";
import { db } from "../db";
import { go, useLive } from "../hooks";
import { itemValue } from "../search";
import type { ItemFields } from "../types";

export default function Item({ id }: { id: string }) {
  const item = useLive(() => db().items.get(id), [id], undefined);
  const release = useLive(async () => (item ? db().releases.get(item.release_id) : undefined), [item?.release_id], undefined);
  const price = useLive(async () => (item ? db().prices.get(item.release_id) : undefined), [item?.release_id], undefined);
  const [fields, setFields] = useState<ItemFields>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (item) setFields(item.fields);
  }, [item?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!item || !release) return <main className="page"><p className="muted">Loading…</p></main>;
  if (item.deleted) return <main className="page"><p>This record was removed.</p><button className="link" onClick={() => go("/")}>Back to collection</button></main>;

  const set = (patch: ItemFields) => {
    setFields({ ...fields, ...patch });
    setSaved(false);
  };
  const save = async () => {
    await updateItem(item.id, { fields });
    setSaved(true);
  };
  const value = itemValue({ ...item, fields }, price);
  const isWant = item.kind === "want";

  return (
    <main className="page">
      <button className="link back" onClick={() => history.back()}>← Back</button>
      <div className="hero">
        <Cover id={release.id} size={132} alt={`${release.artist} — ${release.title}`} />
        <div>
          <h1>{release.title}</h1>
          <p className="lead">{release.artist}</p>
          <p className="muted small">{[release.year, release.country, release.formats[0]].filter(Boolean).join(" · ")}</p>
          <p className="small">{release.labels.map((l) => `${l.name} – ${l.catno}`).join(", ")}</p>
          {isWant ? <span className="badge want">Wantlist</span> : <span className="badge ok">Collection</span>}
          {item.dirty ? <span className="badge pending">Not synced yet</span> : null}
        </div>
      </div>

      <Section title={isWant ? "What I'm looking for" : "My copy"}>
        {isWant ? (
          <label className="field">
            <span>Max price (EUR)</span>
            <input type="number" inputMode="decimal" min="0" step="0.5" value={fields.max_price ?? ""} onChange={(e) => set({ max_price: e.target.value ? Number(e.target.value) : null })} />
          </label>
        ) : (
          <div className="grid2">
            <GradeSelect label="Media grade" value={fields.media_grade} onChange={(v) => set({ media_grade: v })} />
            <GradeSelect label="Sleeve grade" value={fields.sleeve_grade} onChange={(v) => set({ sleeve_grade: v })} />
            <label className="field">
              <span>Paid (EUR)</span>
              <input type="number" inputMode="decimal" min="0" step="0.5" value={fields.purchase_price ?? ""} onChange={(e) => set({ purchase_price: e.target.value ? Number(e.target.value) : null })} />
            </label>
            <label className="field">
              <span>Bought on</span>
              <input type="date" value={fields.purchase_date ?? ""} onChange={(e) => set({ purchase_date: e.target.value })} />
            </label>
            <label className="field">
              <span>Bought at</span>
              <input value={fields.purchase_place ?? ""} onChange={(e) => set({ purchase_place: e.target.value })} />
            </label>
            <label className="field">
              <span>Storage location</span>
              <input value={fields.location ?? ""} placeholder="e.g. Shelf 2" onChange={(e) => set({ location: e.target.value })} />
            </label>
          </div>
        )}
        <label className="field">
          <span>Notes</span>
          <textarea rows={3} value={fields.notes ?? ""} onChange={(e) => set({ notes: e.target.value })} />
        </label>
        <div className="actions">
          <button className="primary" onClick={save}>Save</button>
          {saved && <span className="muted small">Saved on this phone ✓</span>}
        </div>
      </Section>

      {price && (
        <Section title="Last known price" right={!isWant && value != null ? <strong>{eur(value)}</strong> : undefined}>
          <PriceView card={price} grade={fields.media_grade} />
        </Section>
      )}

      <Section title="Details">
        <dl className="details">
          {release.matrix.length > 0 && (<><dt>Runout</dt><dd>{release.matrix.join(" · ")}</dd></>)}
          {release.barcodes.length > 0 && (<><dt>Barcode</dt><dd>{release.barcodes.join(", ")}</dd></>)}
          {release.genres.length > 0 && (<><dt>Genre</dt><dd>{[...release.genres, ...release.styles].join(", ")}</dd></>)}
          <dt>Format</dt><dd>{release.formats.join(" + ")}</dd>
        </dl>
        {release.tracklist.length > 0 && (
          <ol className="tracks">
            {release.tracklist.map((t, i) => (
              <li key={i}><span className="muted">{t.position}</span> {t.title} <span className="muted">{t.duration}</span></li>
            ))}
          </ol>
        )}
      </Section>

      <div className="actions wrap">
        <button className="secondary" onClick={() => go(`/release/${release.id}`)}>Price check (online)</button>
        {release.master_id && <button className="secondary" onClick={() => go(`/pressing/${release.master_id}?release=${release.id}`)}>Other pressings</button>}
        {isWant && <button className="secondary" onClick={() => updateItem(item.id, { kind: "collection" })}>Got it! Move to collection</button>}
        <button className="danger" onClick={async () => {
          if (confirm("Remove this record?")) {
            await removeItem(item.id);
            go("/");
          }
        }}>Remove</button>
      </div>
    </main>
  );
}
