import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorNote } from "../components";
import type { User } from "../types";

export default function Login({ onSignedIn, expectedUser }: { onSignedIn: (u: User) => void; expectedUser?: User | null }) {
  const [status, setStatus] = useState<{ needs_setup: boolean; demo: boolean } | null>(null);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState(expectedUser?.username ?? "");
  const [password, setPassword] = useState("");
  const [invite, setInvite] = useState(new URLSearchParams(window.location.hash.split("?")[1] || "").get("invite") ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ needs_setup: boolean; demo: boolean }>("/api/status")
      .then((s) => {
        setStatus(s);
        if (s.needs_setup || invite) setMode("register");
      })
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await api<User>(mode === "login" ? "/api/login" : "/api/register", {
        method: "POST",
        json: { username, password, invite: invite || undefined },
      });
      onSignedIn(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="page narrow">
      <div className="brand">
        <img src="/icons/icon-192.png" alt="" width={72} height={72} />
        <h1>33Vinyls</h1>
        <p className="muted">Identify records, check prices, keep your collection offline.</p>
      </div>
      {status?.demo && <p className="note">Demo mode: the server uses fictional test records instead of Discogs.</p>}
      <form className="card" onSubmit={submit}>
        <h2>{status?.needs_setup ? "Create the first (admin) account" : mode === "login" ? "Sign in" : "Join with an invite"}</h2>
        <label className="field">
          <span>Username</span>
          <input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required minLength={2} />
        </label>
        <label className="field">
          <span>Password</span>
          <input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
        </label>
        {mode === "register" && !status?.needs_setup && (
          <label className="field">
            <span>Invite code</span>
            <input value={invite} onChange={(e) => setInvite(e.target.value)} required />
          </label>
        )}
        <ErrorNote error={error} />
        <button className="primary" disabled={busy}>
          {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
        </button>
        {!status?.needs_setup && (
          <button type="button" className="link" onClick={() => setMode(mode === "login" ? "register" : "login")}>
            {mode === "login" ? "I have an invite code" : "I already have an account"}
          </button>
        )}
      </form>
      {expectedUser && <p className="muted small">Your records stay on this phone while you sign in again.</p>}
    </main>
  );
}
