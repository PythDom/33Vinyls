import { useEffect, useState, type ReactNode } from "react";
import { db } from "./db";
import { go, useLive } from "./hooks";
import type { Candidate, PriceCard } from "./types";
import { GRADES } from "./types";

export const eur = (v: number | null | undefined) =>
  v == null ? "—" : new Intl.NumberFormat("fr-BE", { style: "currency", currency: "EUR" }).format(v);

/** Cover from the phone's offline store; falls back to the server when online. */
export function Cover({ id, size = 56, alt = "" }: { id: number; size?: number; alt?: string }) {
  const thumb = useLive(() => db().thumbs.get(id), [id], undefined);
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!thumb) {
      setUrl(null);
      return;
    }
    const u = URL.createObjectURL(thumb.blob);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [thumb]);
  const src = url ?? (failed ? null : `/api/thumbs/${id}`);
  return src ? (
    <img className="cover" src={src} alt={alt} width={size} height={size} style={{ width: size, height: size }} onError={() => setFailed(true)} loading="lazy" />
  ) : (
    <div className="cover cover-empty" style={{ width: size, height: size }} aria-hidden>
      ◎
    </div>
  );
}

export function OwnedBadges({ owned }: { owned?: string[] }) {
  if (!owned?.length) return null;
  return (
    <span className="badges">
      {owned.includes("collection") && <span className="badge ok">In your collection</span>}
      {owned.includes("want") && <span className="badge want">On your wantlist</span>}
    </span>
  );
}

export function CandidateList({ candidates, empty }: { candidates: Candidate[]; empty?: string }) {
  if (!candidates.length) return <p className="muted">{empty ?? "No matches."}</p>;
  return (
    <ul className="list">
      {candidates.map((c) => (
        <li key={c.id}>
          <button className="row" onClick={() => go(`/release/${c.id}`)}>
            <img className="cover" src={c.thumb} alt="" width={56} height={56} loading="lazy" />
            <span className="row-text">
              <strong>{c.artist ? `${c.artist} — ` : ""}{c.title}</strong>
              <span className="muted small">
                {[c.year, c.country, c.label && `${c.label} ${c.catno}`, c.format].filter(Boolean).join(" · ")}
              </span>
              {c.matched && c.matched.length > 0 && <span className="small accent">Matched: {c.matched.join(", ")}</span>}
              <OwnedBadges owned={c.owned} />
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function GradeSelect({ value, onChange, label, allowEmpty = true }: { value?: string; onChange: (v: string) => void; label: string; allowEmpty?: boolean }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        {allowEmpty && <option value="">—</option>}
        {GRADES.map((g) => (
          <option key={g} value={g}>
            {g}
          </option>
        ))}
      </select>
    </label>
  );
}

export function PriceView({ card, grade }: { card: PriceCard; grade?: string }) {
  const date = new Date(card.fetched_at).toLocaleDateString();
  const forGrade = grade ? card.suggested?.[grade] : undefined;
  return (
    <div className="price">
      <div className="price-grid">
        <div>
          <span className="muted small">Low</span>
          <strong>{eur(card.low)}</strong>
        </div>
        <div>
          <span className="muted small">Median</span>
          <strong>{eur(card.median)}</strong>
        </div>
        <div>
          <span className="muted small">High</span>
          <strong>{eur(card.high)}</strong>
        </div>
      </div>
      {grade && forGrade != null && (
        <p>
          Suggested for <strong>{grade}</strong>: <strong>{eur(forGrade)}</strong>
        </p>
      )}
      <p className="muted small">
        Cheapest for sale now: {eur(card.lowest)} · {card.num_for_sale ?? "?"} for sale · {card.source}, {date}
        {card.stale ? " (could not refresh)" : ""}
      </p>
      {card.note && <p className="muted small">{card.note}</p>}
    </div>
  );
}

export function Section({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  return error ? (
    <p className="error" role="alert">
      {error}
    </p>
  ) : null;
}
