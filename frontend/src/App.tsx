import { useEffect, useState } from "react";
import { api, ApiError } from "./api";
import { openDB, rememberUser, savedUser } from "./db";
import { go, useHashRoute, useSync } from "./hooks";
import Collection from "./pages/Collection";
import Find from "./pages/Find";
import Friends from "./pages/Friends";
import Item from "./pages/Item";
import Login from "./pages/Login";
import Pressing from "./pages/Pressing";
import Release from "./pages/Release";
import Scan from "./pages/Scan";
import Settings from "./pages/Settings";
import { requestPersistence, resetSyncState, startSync, syncNow } from "./sync";
import type { User } from "./types";

function SyncChip() {
  const s = useSync();
  let text = "Synced";
  let cls = "ok";
  if (s.status === "syncing") [text, cls] = ["Syncing…", "busy"];
  else if (s.status === "offline") [text, cls] = [s.pending > 0 ? `Offline · ${s.pending} to sync` : "Offline", "off"];
  else if (s.status === "signed-out") [text, cls] = ["Sign in to sync", "warn"];
  else if (s.status === "error") [text, cls] = ["Sync problem", "warn"];
  else if (s.pending > 0) [text, cls] = [`${s.pending} to sync`, "busy"];
  return (
    <button className={`sync-chip ${cls}`} onClick={() => go("/settings")} title={s.message}>
      {text}
    </button>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(() => {
    const u = savedUser();
    if (u) openDB(u);
    return u;
  });
  const [relogin, setRelogin] = useState(false);
  const [path, params] = useHashRoute();
  const sync = useSync();

  useEffect(() => {
    if (!user) return;
    startSync();
    // check the session in the background; never block the offline collection
    api<User>("/api/me", { timeout: 5000 })
      .then((me) => rememberUser({ ...user, ...me }))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) setRelogin(true);
      });
  }, [user]);

  useEffect(() => {
    if (sync.status === "signed-out") setRelogin(true);
  }, [sync.status]);

  const signedIn = (u: User) => {
    if (user && user.id !== u.id) resetSyncState();
    rememberUser(u);
    openDB(u);
    setUser(u);
    setRelogin(false);
    void requestPersistence();
    void syncNow();
    go("/");
  };

  if (!user || relogin || path === "/login") {
    return <Login onSignedIn={signedIn} expectedUser={user} />;
  }

  const [, section, arg] = path.split("/");
  let page;
  switch (section) {
    case "item":
      page = <Item id={arg} />;
      break;
    case "scan":
      page = <Scan />;
      break;
    case "find":
      page = <Find initial={params} key={params.toString()} />;
      break;
    case "release":
      page = <Release id={Number(arg)} key={arg} />;
      break;
    case "pressing":
      page = <Pressing masterId={Number(arg)} params={params} key={arg} />;
      break;
    case "friends":
      page = <Friends friendId={arg} params={params} key={`${arg}-${params.get("kind")}`} />;
      break;
    case "settings":
      page = <Settings user={user} onSignOut={() => { rememberUser(null); resetSyncState(); setUser(null); go("/"); }} />;
      break;
    default:
      page = <Collection />;
  }

  const tab = section || "collection";
  return (
    <div className="app">
      <header className="topbar">
        <button className="brand-mini" onClick={() => go("/")}>
          <img src="/icons/icon-192.png" alt="" width={28} height={28} /> 33Vinyls
        </button>
        <SyncChip />
      </header>
      {page}
      <nav className="tabbar" aria-label="Main">
        <button aria-current={["collection", "item"].includes(tab)} onClick={() => go("/")}>
          <span aria-hidden>▤</span>Records
        </button>
        <button aria-current={tab === "scan"} onClick={() => go("/scan")}>
          <span aria-hidden>⌁</span>Scan
        </button>
        <button aria-current={["find", "release", "pressing"].includes(tab)} onClick={() => go("/find")}>
          <span aria-hidden>⌕</span>Find
        </button>
        <button aria-current={["settings", "friends"].includes(tab)} onClick={() => go("/settings")}>
          <span aria-hidden>⚙</span>Settings
        </button>
      </nav>
    </div>
  );
}
