import { useEffect, useState } from "react";
import { api } from "../api";
import { CandidateList, ErrorNote } from "../components";
import { useOnline } from "../hooks";
import type { Candidate } from "../types";

export default function Find({ initial }: { initial: URLSearchParams }) {
  const online = useOnline();
  const [q, setQ] = useState(initial.get("q") ?? "");
  const [catno, setCatno] = useState(initial.get("catno") ?? "");
  const [results, setResults] = useState<Candidate[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!q.trim() && !catno.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const params = new URLSearchParams({ q, catno });
      setResults((await api<{ candidates: Candidate[] }>(`/api/search?${params}`, { timeout: 15000 })).candidates);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (initial.get("q") || initial.get("catno")) void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="page">
      <h1>Find on Discogs</h1>
      {!online && <p className="note">You're offline. Searching Discogs needs a connection; your own collection can still be searched on the Collection tab.</p>}
      <form className="card" onSubmit={(e) => { e.preventDefault(); void run(); }}>
        <label className="field">
          <span>Artist, title…</span>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Velvet Static Neon Harbour" />
        </label>
        <label className="field">
          <span>Catalogue number (optional)</span>
          <input value={catno} onChange={(e) => setCatno(e.target.value)} placeholder="e.g. HL 2001" />
        </label>
        <button className="primary" disabled={busy || !online}>{busy ? "Searching…" : "Search"}</button>
      </form>
      <ErrorNote error={error} />
      {results && <CandidateList candidates={results} />}
    </main>
  );
}
