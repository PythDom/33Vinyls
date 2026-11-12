import { useEffect, useMemo, useRef, useState } from "react";
import { api, shrinkPhoto, upload } from "../api";
import { CandidateList, Cover, ErrorNote, Section } from "../components";
import { db } from "../db";
import { go, useLive, useOnline } from "../hooks";
import { buildRows, matchBarcode } from "../search";
import type { Candidate } from "../types";

interface BarcodeDetectorLike {
  detect(source: CanvasImageSource): Promise<{ rawValue: string }[]>;
}
declare global {
  interface Window {
    BarcodeDetector?: new (opts: { formats: string[] }) => BarcodeDetectorLike;
  }
}

const hasDetector = typeof window !== "undefined" && "BarcodeDetector" in window;

export default function Scan() {
  const online = useOnline();
  const items = useLive(() => db().items.toArray(), [], []);
  const releases = useLive(async () => new Map((await db().releases.toArray()).map((r) => [r.id, r])), [], new Map());
  const rows = useMemo(() => buildRows(items, releases, new Map()), [items, releases]);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [scanning, setScanning] = useState(false);
  const [code, setCode] = useState("");
  const [manual, setManual] = useState("");
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
  const [ocr, setOcr] = useState<{ words: string[]; tried: { kind: string; value: string; results: number }[] } | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const resultsRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (candidates || ocr || code) resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [candidates, ocr, code]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const stop = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setScanning(false);
  };
  useEffect(() => stop, []);

  const lookup = async (raw: string) => {
    const digits = raw.replace(/\D/g, "");
    setCode(digits);
    setCandidates(null);
    setOcr(null);
    setError(null);
    if (!online) return;
    setBusy("Looking up barcode…");
    try {
      const r = await api<{ candidates: Candidate[] }>(`/api/identify/barcode?code=${digits}`);
      setCandidates(r.candidates);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lookup failed");
    } finally {
      setBusy(null);
    }
  };

  const start = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: { ideal: 1280 } }, audio: false });
      streamRef.current = stream;
      setScanning(true);
      const video = videoRef.current!;
      video.srcObject = stream;
      await video.play();
      const detector = new window.BarcodeDetector!({ formats: ["ean_13", "ean_8", "upc_a", "upc_e"] });
      const tick = async () => {
        if (!streamRef.current) return;
        try {
          const found = await detector.detect(video);
          if (found.length) {
            if (navigator.vibrate) navigator.vibrate(60);
            stop();
            void lookup(found[0].rawValue);
            return;
          }
        } catch {
          /* frame not ready */
        }
        setTimeout(tick, 180);
      };
      void tick();
    } catch {
      setError("Camera not available. Allow camera access, or type the barcode below.");
      stop();
    }
  };

  const onPhoto = async (file: File | undefined, mode: "cover" | "label" | "barcode") => {
    if (!file) return;
    setError(null);
    setCandidates(null);
    setOcr(null);
    setCode("");
    const blob = await shrinkPhoto(file, mode === "barcode" ? 2000 : 1600);
    try {
      if (mode === "barcode") {
        setBusy("Reading barcode…");
        const r = await upload<{ codes: string[] }>("/api/identify/barcode-photo", blob);
        if (!r.codes.length) setError("No barcode found in the photo. Try closer, with good light.");
        else await lookup(r.codes[0]);
      } else {
        setBusy(mode === "cover" ? "Reading the cover…" : "Reading the label…");
        const r = await upload<{ candidates: Candidate[]; words: string[]; tried: { kind: string; value: string; results: number }[] }>("/api/identify/photo", blob, { mode });
        setCandidates(r.candidates);
        setOcr({ words: r.words ?? [], tried: r.tried ?? [] });
        setPicked([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  };

  const localMatches = code ? matchBarcode(rows, code) : [];

  return (
    <main className="page">
      <h1>Scan a record</h1>
      <Section title="Barcode">
        {hasDetector ? (
          <>
            <div className={scanning ? "viewfinder on" : "viewfinder"}>
              <video ref={videoRef} playsInline muted />
              {scanning && <div className="aim" />}
            </div>
            {scanning ? (
              <button className="secondary wide" onClick={stop}>Stop camera</button>
            ) : (
              <button className="primary wide" onClick={start}>Scan barcode with camera</button>
            )}
          </>
        ) : (
          <label className="primary wide filebtn">
            Take a photo of the barcode
            <input type="file" accept="image/*" capture="environment" onChange={(e) => onPhoto(e.target.files?.[0], "barcode")} hidden disabled={!online} />
          </label>
        )}
        <form className="inline" onSubmit={(e) => { e.preventDefault(); void lookup(manual); }}>
          <input inputMode="numeric" placeholder="or type the barcode digits" value={manual} onChange={(e) => setManual(e.target.value)} aria-label="Barcode digits" />
          <button className="secondary">Check</button>
        </form>
      </Section>

      <Section title="Photo of cover or label" right={!online ? <span className="muted small">needs connection</span> : undefined}>
        <div className="actions">
          <label className={online ? "secondary filebtn" : "secondary filebtn disabled"}>
            📷 Cover
            <input type="file" accept="image/*" capture="environment" onChange={(e) => onPhoto(e.target.files?.[0], "cover")} hidden disabled={!online} />
          </label>
          <label className={online ? "secondary filebtn" : "secondary filebtn disabled"}>
            📷 Centre label
            <input type="file" accept="image/*" capture="environment" onChange={(e) => onPhoto(e.target.files?.[0], "label")} hidden disabled={!online} />
          </label>
        </div>
        <p className="muted small">For the exact pressing, pick the album first, then use “Which pressing?” and the runout.</p>
      </Section>

      <div ref={resultsRef} className="scroll-anchor" />
      {busy && <p className="busy" aria-live="polite">{busy}</p>}
      <ErrorNote error={error} />

      {code && (
        <Section title={`Barcode ${code}`}>
          {localMatches.length > 0 ? (
            <ul className="list">
              {localMatches.map(({ item, release }) => (
                <li key={item.id}>
                  <button className="row" onClick={() => go(`/item/${item.id}`)}>
                    <Cover id={release.id} />
                    <span className="row-text">
                      <strong>{release.artist} — {release.title}</strong>
                      <span className={item.kind === "want" ? "badge want" : "badge ok"}>{item.kind === "want" ? "On your wantlist" : "You own this"}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Not in your collection or wantlist.</p>
          )}
          {!online && <p className="muted small">Offline: connect to look it up on Discogs.</p>}
        </Section>
      )}

      {candidates && (
        <Section title="Matches on Discogs">
          <CandidateList candidates={candidates} empty="No match found from the photo. Pick the right words below, or search by text." />
        </Section>
      )}
      {ocr && (
        <Section title="Words read on the photo">
          {ocr.words.length ? (
            <>
              <p className="muted small">Tap the artist or title words (spelling can be fixed on the next screen), then search.</p>
              <div className="options">
                {ocr.words.map((w) => (
                  <button key={w} className={picked.includes(w) ? "chip active" : "chip"} aria-pressed={picked.includes(w)}
                    onClick={() => setPicked(picked.includes(w) ? picked.filter((p) => p !== w) : [...picked, w])}>
                    {w}
                  </button>
                ))}
              </div>
              <button className="primary" disabled={!picked.length} onClick={() => go(`/find?q=${encodeURIComponent(picked.join(" "))}`)}>
                Search with {picked.length || "selected"} word{picked.length === 1 ? "" : "s"}
              </button>
            </>
          ) : (
            <p className="muted">Nothing readable. Try again closer, with even light and no glare, or use the barcode or text search.</p>
          )}
          {ocr.tried.length > 0 && (
            <p className="muted small">Searched Discogs for: {ocr.tried.map((t) => `“${t.value}” (${t.results})`).join(", ")}</p>
          )}
        </Section>
      )}
      {(candidates || ocr) && <button className="link" onClick={() => go("/find")}>Search by text instead</button>}
    </main>
  );
}
