import { useEffect, useState } from "react";
import { addRelease } from "../actions";
import { api } from "../api";
import { Cover, ErrorNote, FriendBadges, GradeSelect, OwnedBadges, PriceView, Section, eur } from "../components";
import { db } from "../db";
import { go, useLive } from "../hooks";
import type { PriceCard, Release as R } from "../types";

interface Deal {
  estimate: number | null;
  verdict: "green" | "amber" | "red" | "unknown";
  ratio: number | null;
}

const VERDICT_TEXT = { green: "Good deal", amber: "Fair price", red: "Expensive", unknown: "No price data" };

export default function Release({ id }: { id: number }) {
  const local = useLive(() => db().releases.get(id), [id], undefined);
  const localItems = useLive(() => db().items.where("release_id").equals(id).filter((i) => !i.deleted).toArray(), [id], []);
  const [release, setRelease] = useState<R | null>(null);
  const [price, setPrice] = useState<PriceCard | null>(null);
  const [media, setMedia] = useState("VG+");
  const [sleeve, setSleeve] = useState("VG+");
  const [asking, setAsking] = useState("");
  const [deal, setDeal] = useState<Deal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [priceError, setPriceError] = useState<string | null>(null);
  const [added, setAdded] = useState<string | null>(null);

  useEffect(() => {
    setRelease(null);
    setPrice(null);
    api<R>(`/api/releases/${id}`, { timeout: 15000 }).then(setRelease).catch((e) => setError(e.message));
    api<PriceCard>(`/api/releases/${id}/price`, { timeout: 20000 }).then(setPrice).catch((e) => setPriceError(e.message));
  }, [id]);

  const r = release ?? local ?? null;
  if (!r) return <main className="page">{error ? <ErrorNote error={error} /> : <p className="muted">Loading…</p>}</main>;

  const checkDeal = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setDeal(await api<Deal>(`/api/releases/${id}/deal`, { method: "POST", json: { asking: Number(asking), media, sleeve } }));
    } catch (err) {
      setPriceError(err instanceof Error ? err.message : "Failed");
    }
  };

  const add = async (kind: "collection" | "want") => {
    const fields = kind === "collection" ? { media_grade: media, sleeve_grade: sleeve, ...(asking ? { purchase_price: Number(asking) } : {}) } : {};
    const itemId = await addRelease(r, kind, fields, price);
    setAdded(itemId);
  };

  const ownedKinds = localItems.map((i) => i.kind);

  return (
    <main className="page">
      <button className="link back" onClick={() => history.back()}>← Back</button>
      <div className="hero">
        <Cover id={r.id} size={132} alt={`${r.artist} — ${r.title}`} />
        <div>
          <h1>{r.title}</h1>
          <p className="lead">{r.artist}</p>
          <p className="muted small">{[r.year, r.country, r.formats[0]].filter(Boolean).join(" · ")}</p>
          <p className="small">{r.labels.map((l) => `${l.name} – ${l.catno}`).join(", ")}</p>
          <OwnedBadges owned={ownedKinds} />
          <FriendBadges friends={release?.friends} />
        </div>
      </div>
      {!release && error && <p className="note">Showing the copy saved on this phone. {error}</p>}

      <Section title="Price (EUR)">
        <div className="grid2">
          <GradeSelect label="Media" value={media} onChange={setMedia} allowEmpty={false} />
          <GradeSelect label="Sleeve" value={sleeve} onChange={setSleeve} allowEmpty={false} />
        </div>
        {price ? <PriceView card={price} grade={media} /> : priceError ? <ErrorNote error={priceError} /> : <p className="muted">Loading prices…</p>}
        <form className="inline" onSubmit={checkDeal}>
          <input type="number" inputMode="decimal" min="0" step="0.5" placeholder="Shop price €" value={asking} onChange={(e) => setAsking(e.target.value)} aria-label="Shop price in euro" />
          <button className="secondary" disabled={!asking}>Is it a deal?</button>
        </form>
        {deal && (
          <p className={`verdict ${deal.verdict}`} role="status">
            <strong>{VERDICT_TEXT[deal.verdict]}</strong>
            {deal.estimate != null && <> · estimate {eur(deal.estimate)}{deal.ratio != null && ` · asking is ${Math.round(deal.ratio * 100)}%`}</>}
          </p>
        )}
      </Section>

      <div className="actions wrap">
        <button className="primary" onClick={() => add("collection")}>Add to collection ({media})</button>
        <button className="secondary" onClick={() => add("want")}>Add to wantlist</button>
        {r.master_id && <button className="secondary" onClick={() => go(`/pressing/${r.master_id}?release=${r.id}`)}>Which pressing?</button>}
      </div>
      {added && (
        <p className="note">
          Saved on this phone ✓ <button className="link" onClick={() => go(`/item/${added}`)}>Open</button>
        </p>
      )}

      <Section title="Details">
        <dl className="details">
          {r.matrix.length > 0 && (<><dt>Runout</dt><dd>{r.matrix.join(" · ")}</dd></>)}
          {r.barcodes.length > 0 && (<><dt>Barcode</dt><dd>{r.barcodes.join(", ")}</dd></>)}
          <dt>Format</dt><dd>{r.formats.join(" + ")}</dd>
          {r.genres.length > 0 && (<><dt>Genre</dt><dd>{[...r.genres, ...r.styles].join(", ")}</dd></>)}
        </dl>
        {r.tracklist.length > 0 && (
          <ol className="tracks">
            {r.tracklist.map((t, i) => (<li key={i}><span className="muted">{t.position}</span> {t.title} <span className="muted">{t.duration}</span></li>))}
          </ol>
        )}
        <p className="muted small">Data from Discogs. <a href={r.discogs_url} target="_blank" rel="noreferrer">View on Discogs</a></p>
      </Section>
    </main>
  );
}
