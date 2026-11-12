import { liveQuery } from "dexie";
import { useEffect, useState, useSyncExternalStore } from "react";
import { getSyncState, subscribeSync } from "./sync";

/** Re-runs a Dexie query whenever the local database changes. */
export function useLive<T>(query: () => Promise<T>, deps: unknown[], initial: T): T {
  const [value, setValue] = useState<T>(initial);
  useEffect(() => {
    const sub = liveQuery(query).subscribe({ next: setValue, error: (e) => console.error(e) });
    return () => sub.unsubscribe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return value;
}

export function useSync() {
  return useSyncExternalStore(subscribeSync, getSyncState);
}

export function useHashRoute(): [string, URLSearchParams] {
  const read = () => window.location.hash.replace(/^#/, "") || "/";
  const [hash, setHash] = useState(read);
  useEffect(() => {
    const onChange = () => setHash(read());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const [path, query = ""] = hash.split("?");
  return [path, new URLSearchParams(query)];
}

export function go(path: string) {
  window.location.hash = path;
}

export function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}
