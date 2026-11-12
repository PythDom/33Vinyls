import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorNote, Section } from "../components";
import { db } from "../db";
import { useLive, useSync } from "../hooks";
import { requestPersistence, syncNow } from "../sync";
import type { User } from "../types";

interface DiscogsStatus {
  linked: boolean;
  username?: string;
  method?: string;
  demo: boolean;
  oauth_available: boolean;
}

export default function Settings({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const sync = useSync();
  const counts = useLive(async () => ({
    records: await db().items.filter((i) => !i.deleted).count(),
    thumbs: await db().thumbs.count(),
  }), [], { records: 0, thumbs: 0 });
  const [persisted, setPersisted] = useState<boolean | null>(null);
  const [usage, setUsage] = useState<string>("");
  const [discogs, setDiscogs] = useState<DiscogsStatus | null>(null);
  const [token, setToken] = useState("");
  const [invites, setInvites] = useState<{ code: string; used_by: string | null; created_at: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const flag = new URLSearchParams(window.location.hash.split("?")[1] || "").get("discogs");

  const loadOnline = () => {
    api<{ discogs: DiscogsStatus }>("/api/me").then((m) => setDiscogs(m.discogs)).catch(() => setDiscogs(null));
    if (user.is_admin) api<typeof invites>("/api/invites").then(setInvites).catch(() => undefined);
  };

  useEffect(() => {
    navigator.storage?.persisted?.().then(setPersisted).catch(() => setPersisted(null));
    navigator.storage?.estimate?.().then((e) => setUsage(e.usage ? `${(e.usage / 1048576).toFixed(1)} MB used` : "")).catch(() => undefined);
    loadOnline();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const linkToken = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      setDiscogs(await api<DiscogsStatus>("/api/discogs/token", { method: "POST", json: { token }, timeout: 20000 }));
      setToken("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  };

  const oauth = async () => {
    setError(null);
    try {
      const { url } = await api<{ url: string }>("/api/discogs/oauth/start", { timeout: 20000 });
      window.location.href = url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  };

  const unlink = async () => {
    if (!confirm("Disconnect your Discogs account from 33Vinyls?")) return;
    setDiscogs(await api<DiscogsStatus>("/api/discogs/link", { method: "DELETE" }));
  };

  const newInvite = async () => {
    try {
      const { code } = await api<{ code: string }>("/api/invites", { method: "POST" });
      loadOnline();
      const link = `${window.location.origin}/#/login?invite=${code}`;
      try {
        await navigator.clipboard.writeText(link);
        alert(`Invite link copied:\n${link}`);
      } catch {
        prompt("Send this invite link to your friend:", link);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  };

  const signOut = async () => {
    if (sync.pending > 0 && !confirm(`${sync.pending} change(s) are not synced yet and will be lost. Sign out anyway?`)) return;
    try {
      await api("/api/logout", { method: "POST" });
    } catch {
      /* offline: still sign out locally */
    }
    onSignOut();
  };

  return (
    <main className="page">
      <h1>Settings</h1>
      <ErrorNote error={error} />

      <Section title="Offline">
        <p className={sync.offlineReady ? "ok-text" : ""}>
          {sync.offlineReady ? "✓ Offline ready" : "Not fully offline yet"} — {counts.records} records, {counts.thumbs} covers on this phone
        </p>
        <ul className="plain small">
          <li>Last sync: {sync.lastSync ? new Date(sync.lastSync).toLocaleString() : "never"}</li>
          <li>Changes waiting to sync: {sync.pending}</li>
          {sync.thumbsMissing > 0 && <li>Covers still to download: {sync.thumbsMissing}</li>}
          <li>
            Protected storage: {persisted ? "yes ✓" : persisted === false ? "no — Android may clear data when space is low" : "unknown"} {usage && `· ${usage}`}
          </li>
        </ul>
        <div className="actions">
          <button className="secondary" onClick={() => void syncNow()}>Sync now</button>
          {!persisted && <button className="secondary" onClick={async () => setPersisted(await requestPersistence())}>Protect storage</button>}
        </div>
        {sync.message && <p className="muted small">{sync.message}</p>}
      </Section>

      <Section title="Discogs account">
        {flag === "linked" && <p className="ok-text">Discogs account linked ✓</p>}
        {flag === "failed" && <p className="error">Discogs sign-in didn't complete. Try again.</p>}
        {!discogs ? (
          <p className="muted">Needs a connection to the server.</p>
        ) : discogs.demo ? (
          <p className="muted">Demo mode: the server uses fictional test records, no Discogs account needed.</p>
        ) : discogs.linked ? (
          <>
            <p>Linked as <strong>{discogs.username}</strong> ({discogs.method === "oauth" ? "Discogs sign-in" : "personal token"}).</p>
            <p className="muted small">For per-condition price suggestions, fill in your Discogs seller settings with currency EUR.</p>
            <button className="secondary" onClick={unlink}>Disconnect</button>
          </>
        ) : (
          <>
            <p>Link your own Discogs account to look up records and prices.</p>
            {discogs.oauth_available && <button className="primary" onClick={oauth}>Sign in with Discogs</button>}
            <form onSubmit={linkToken}>
              <label className="field">
                <span>{discogs.oauth_available ? "Or paste a personal access token" : "Personal access token (Discogs → Settings → Developers)"}</span>
                <input value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" />
              </label>
              <button className="secondary" disabled={token.length < 10}>Link with token</button>
            </form>
          </>
        )}
      </Section>

      {user.is_admin && (
        <Section title="Invite friends" right={<button className="secondary" onClick={newInvite}>New invite</button>}>
          <p className="muted small">Friends must first be able to reach this server through your Tailscale network.</p>
          <ul className="plain small">
            {invites.map((i) => (
              <li key={i.code}>
                <code>{i.code}</code> {i.used_by ? `— used by ${i.used_by}` : "— not used yet"}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Account">
        <p>Signed in as <strong>{user.display_name}</strong>{user.is_admin ? " (admin)" : ""}</p>
        <button className="danger" onClick={signOut}>Sign out</button>
      </Section>
      <p className="muted small center">33Vinyls {__APP_VERSION__}</p>
    </main>
  );
}
