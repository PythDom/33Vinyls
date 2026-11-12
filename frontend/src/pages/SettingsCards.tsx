import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { ErrorNote, Section } from "../components";
import { go } from "../hooks";
import { syncNow } from "../sync";

interface ImportStatus {
  state: "idle" | "running" | "done" | "error";
  step?: string;
  seen?: number;
  added?: number;
  skipped?: number;
  error?: string | null;
}

export function ImportCard({ linked }: { linked: boolean }) {
  const [status, setStatus] = useState<ImportStatus>({ state: "idle" });
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const poll = async () => {
    try {
      const s = await api<ImportStatus>("/api/discogs/import");
      setStatus(s);
      if (s.state === "running") timer.current = setTimeout(poll, 1000);
      else if (s.state === "done") void syncNow();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  };
  useEffect(() => {
    void poll();
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const start = async () => {
    setError(null);
    try {
      setStatus(await api<ImportStatus>("/api/discogs/import", { method: "POST", json: { collection: true, wantlist: true } }));
      timer.current = setTimeout(poll, 800);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  };

  return (
    <Section title="Import from Discogs">
      <p className="muted small">Copies your Discogs collection (with grades and notes) and wantlist. Records already imported are skipped, so you can run it again later.</p>
      {status.state === "running" && (
        <p aria-live="polite">Importing {status.step}… {status.added ?? 0} added, {status.skipped ?? 0} already here</p>
      )}
      {status.state === "done" && (
        <p className="ok-text">✓ Import finished: {status.added} added, {status.skipped} already here. Barcodes, runouts and prices are filled in over the next minutes.</p>
      )}
      {status.state === "error" && <p className="error">{status.error}</p>}
      <ErrorNote error={error} />
      <button className="secondary" disabled={!linked || status.state === "running"} onClick={start}>
        {status.state === "done" ? "Import again" : "Import collection & wantlist"}
      </button>
      {!linked && <p className="muted small">Link your Discogs account first.</p>}
    </Section>
  );
}

interface Sharing {
  share_collection: boolean;
  share_wantlist: boolean;
  share_values: boolean;
}

export function SharingCard() {
  const [s, setS] = useState<Sharing | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<Sharing>("/api/sharing").then(setS).catch(() => setS(null));
  }, []);
  if (!s) return null;
  const save = async (patch: Partial<Sharing>) => {
    const before = s;
    const next = { ...s, ...patch };
    setS(next); // switch immediately; undo if the server can't be reached
    setError(null);
    try {
      setS(await api<Sharing>("/api/sharing", { method: "PUT", json: next }));
    } catch (e) {
      setS(before);
      setError(e instanceof Error ? e.message : "Failed");
    }
  };
  const sharesSomething = s.share_collection || s.share_wantlist;
  return (
    <Section title="Sharing with friends" right={sharesSomething ? <button className="link" onClick={() => go("/friends")}>Friends' records</button> : undefined}>
      <p className="muted small">Off by default. You see friends' records only if you share something too. Changes apply immediately.</p>
      <label className="switch"><span>Share my collection</span><input type="checkbox" checked={s.share_collection} onChange={(e) => save({ share_collection: e.target.checked })} /></label>
      <label className="switch"><span>Share my wantlist</span><input type="checkbox" checked={s.share_wantlist} onChange={(e) => save({ share_wantlist: e.target.checked })} /></label>
      <label className="switch"><span>Show estimated values</span><input type="checkbox" disabled={!sharesSomething} checked={s.share_values} onChange={(e) => save({ share_values: e.target.checked })} /></label>
      <p className="muted small">Purchase prices, notes and storage locations are never shared.</p>
      <ErrorNote error={error} />
    </Section>
  );
}

export function ExportCard() {
  return (
    <Section title="Download my records">
      <p className="muted small">CSV files that open in Excel (EUR format).</p>
      <div className="actions wrap">
        <a className="secondary" href="/api/export/collection.csv" download>Collection (.csv)</a>
        <a className="secondary" href="/api/export/wantlist.csv" download>Wantlist (.csv)</a>
      </div>
    </Section>
  );
}

interface BackupStatus {
  available: boolean;
  problem: string;
  last_export_at: string | null;
  last_export_file: string | null;
  last_export_reason: string | null;
  changes_since_export: number;
  nightly_at: string;
  last_restore_at: string | null;
  files: { file: string; modified: string; size: number }[];
}

export function BackupsCard() {
  const [s, setS] = useState<BackupStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [file, setFile] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const load = () => api<BackupStatus>("/api/admin/backups").then(setS).catch((e) => setError(e.message));
  useEffect(() => {
    void load();
  }, []);

  const exportNow = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ snapshot: string }>("/api/admin/backups/export", { method: "POST", timeout: 120000 });
      setMessage(`Exported ${r.snapshot}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  };
  const restore = async () => {
    setBusy(true);
    setError(null);
    try {
      await api("/api/admin/backups/restore", { method: "POST", json: { file, confirm: confirmed }, timeout: 120000 });
      setMessage(`Restored ${file}. Phones download everything again on their next sync.`);
      setConfirmed(false);
      await load();
      void syncNow();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  if (!s) return <Section title="Backups (OneDrive)"><ErrorNote error={error} /></Section>;
  return (
    <Section title="Backups (OneDrive)">
      {!s.available ? (
        <p className="error">{s.problem}</p>
      ) : (
        <>
          <ul className="plain small">
            <li>Last export: {s.last_export_at ? `${new Date(s.last_export_at).toLocaleString()} (${s.last_export_reason})` : "never"}</li>
            <li>Automatic: every night at {s.nightly_at}, and 10 minutes after 25+ changes</li>
            <li>Changes since last export: {s.changes_since_export}</li>
          </ul>
          <button className="secondary" disabled={busy} onClick={exportNow}>Export now</button>
          <details>
            <summary>Restore from a backup…</summary>
            <p className="muted small">Replaces all data with the chosen copy. The current data is saved first. Put a file in the Sync\restore folder to restore it.</p>
            <select value={file} onChange={(e) => setFile(e.target.value)} aria-label="Backup file">
              <option value="">Choose a backup</option>
              {s.files.map((f) => (
                <option key={f.file} value={f.file}>{f.file} ({Math.round(f.size / 1024)} KB)</option>
              ))}
            </select>
            <label className="switch"><span>I understand this replaces the current data</span><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /></label>
            <button className="danger" disabled={!file || !confirmed || busy} onClick={restore}>Restore</button>
          </details>
        </>
      )}
      {message && <p className="ok-text">{message}</p>}
      <ErrorNote error={error} />
    </Section>
  );
}
