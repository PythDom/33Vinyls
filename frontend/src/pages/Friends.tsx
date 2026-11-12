import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorNote, eur } from "../components";
import { go } from "../hooks";

interface Friend {
  id: number;
  name: string;
  collection: number | null;
  wantlist: number | null;
}
interface FriendItem {
  artist: string;
  title: string;
  year: number | "";
  country: string;
  label: string;
  catno: string;
  media_grade: string;
  release_id: number;
  value?: number | null;
  mine: "collection" | "want" | null;
}

export default function Friends({ friendId, params }: { friendId?: string; params: URLSearchParams }) {
  const [list, setList] = useState<{ you_share: boolean; friends: Friend[] } | null>(null);
  const [items, setItems] = useState<{ friend: string; items: FriendItem[] } | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const kind = params.get("kind") === "want" ? "want" : "collection";

  useEffect(() => {
    setError(null);
    if (friendId) {
      setItems(null);
      api<{ friend: string; items: FriendItem[] }>(`/api/friends/${friendId}/items?kind=${kind}`).then(setItems).catch((e) => setError(e.message));
    } else {
      api<{ you_share: boolean; friends: Friend[] }>("/api/friends").then(setList).catch((e) => setError(e.message));
    }
  }, [friendId, kind]);

  if (friendId) {
    const shown = (items?.items ?? []).filter((i) => !filter || `${i.artist} ${i.title} ${i.label} ${i.catno}`.toLowerCase().includes(filter.toLowerCase()));
    return (
      <main className="page">
        <button className="link back" onClick={() => go("/friends")}>← Friends</button>
        <h1>{items?.friend ?? "…"}: {kind === "want" ? "wantlist" : "collection"}</h1>
        <ErrorNote error={error} />
        <input type="search" placeholder="Filter" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter friend's records" />
        <p className="muted small summary">{shown.length} records</p>
        <ul className="list">
          {shown.map((i, n) => (
            <li key={n}>
              <button className="row" onClick={() => go(`/release/${i.release_id}`)}>
                <img className="cover" src={`/api/thumbs/${i.release_id}`} alt="" width={56} height={56} loading="lazy" />
                <span className="row-text">
                  <strong>{i.artist} — {i.title}</strong>
                  <span className="muted small">{[i.year, i.country, `${i.label} ${i.catno}`, i.media_grade].filter(Boolean).join(" · ")}</span>
                  {i.mine && <span className={i.mine === "want" ? "badge want" : "badge ok"}>{i.mine === "want" ? "On your wantlist" : "You have it too"}</span>}
                </span>
                {i.value != null && <span className="value">{eur(i.value)}</span>}
              </button>
            </li>
          ))}
        </ul>
      </main>
    );
  }

  return (
    <main className="page">
      <h1>Friends</h1>
      <ErrorNote error={error} />
      {list && !list.you_share && (
        <p className="note">Turn on sharing in Settings to see what friends share. Sharing is mutual.</p>
      )}
      {list?.you_share && list.friends.length === 0 && <p className="muted">No friend shares their records yet.</p>}
      <ul className="list">
        {list?.friends.map((f) => (
          <li key={f.id} className="card">
            <strong>{f.name}</strong>
            <div className="actions wrap">
              {f.collection != null && <button className="secondary" onClick={() => go(`/friends/${f.id}?kind=collection`)}>Collection ({f.collection})</button>}
              {f.wantlist != null && <button className="secondary" onClick={() => go(`/friends/${f.id}?kind=want`)}>Wantlist ({f.wantlist})</button>}
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
