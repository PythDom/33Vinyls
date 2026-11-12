import { useEffect, useState } from "react";
import { api, shrinkPhoto, upload } from "../api";
import { CandidateList, ErrorNote, Section } from "../components";
import type { Candidate } from "../types";

interface Question {
  attribute: string;
  question: string;
  options: string[];
}

interface MatchResult {
  candidates: Candidate[];
  total: number;
  question: Question | null;
}

export default function Pressing({ masterId, params }: { masterId: number; params: URLSearchParams }) {
  const [catno, setCatno] = useState(params.get("catno") ?? "");
  const [barcode, setBarcode] = useState(params.get("barcode") ?? "");
  const [matrix, setMatrix] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [skipped, setSkipped] = useState<string[]>([]);
  const [result, setResult] = useState<MatchResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (nextAnswers = answers, nextSkipped = skipped) => {
    setBusy("Comparing pressings…");
    setError(null);
    try {
      const r = await api<MatchResult>("/api/pressing/match", {
        method: "POST",
        json: { master_id: masterId, catno, barcode, matrix, answers: nextAnswers, skip: nextSkipped },
        timeout: 60000,
      });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [masterId]);

  const answer = (attr: string, value: string) => {
    const next = { ...answers, [attr]: value };
    setAnswers(next);
    void run(next);
  };
  const skip = (attr: string) => {
    const next = [...skipped, attr];
    setSkipped(next);
    void run(answers, next);
  };
  const undo = () => {
    setAnswers({});
    setSkipped([]);
    void run({}, []);
  };

  const runoutPhoto = async (file?: File) => {
    if (!file) return;
    setBusy("Reading the runout…");
    try {
      const r = await upload<{ lines: string[] }>("/api/identify/photo", await shrinkPhoto(file, 2000), { mode: "runout" });
      const best = r.lines.sort((a, b) => b.length - a.length)[0] ?? "";
      setMatrix(best);
      if (!best) setError("No text found. Tilt the record so the light catches the etching, or type it.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  };

  const q = result?.question;
  return (
    <main className="page">
      <button className="link back" onClick={() => history.back()}>← Back</button>
      <h1>Which pressing?</h1>
      <Section title="What's on your copy">
        <label className="field">
          <span>Runout / matrix (etched near the label)</span>
          <input value={matrix} onChange={(e) => setMatrix(e.target.value)} placeholder="e.g. HL-2001-A2" autoCapitalize="characters" />
        </label>
        <label className="secondary filebtn small-btn">
          📷 Read runout from photo
          <input type="file" accept="image/*" capture="environment" hidden onChange={(e) => runoutPhoto(e.target.files?.[0])} />
        </label>
        <p className="muted small">Etched text is hard to read automatically: check and correct it before comparing.</p>
        <div className="grid2">
          <label className="field">
            <span>Catalogue number</span>
            <input value={catno} onChange={(e) => setCatno(e.target.value)} />
          </label>
          <label className="field">
            <span>Barcode</span>
            <input inputMode="numeric" value={barcode} onChange={(e) => setBarcode(e.target.value)} />
          </label>
        </div>
        <button className="primary" onClick={() => run()} disabled={!!busy}>Compare</button>
      </Section>

      {q && (
        <Section title="Quick question" right={<button className="link" onClick={() => skip(q.attribute)}>Not sure</button>}>
          <p>{q.question}</p>
          <div className="options">
            {q.options.map((o) => (
              <button key={o} className="chip" onClick={() => answer(q.attribute, o)}>{o}</button>
            ))}
          </div>
        </Section>
      )}
      {(Object.keys(answers).length > 0 || skipped.length > 0) && (
        <p className="muted small">
          Answers: {Object.entries(answers).map(([k, v]) => `${k}: ${v}`).join(", ") || "none"} <button className="link" onClick={undo}>Start over</button>
        </p>
      )}

      {busy && <p className="busy" aria-live="polite">{busy}</p>}
      <ErrorNote error={error} />
      {result && (
        <Section title={result.total === 1 ? "Your pressing" : `${result.total} possible pressings`}>
          <CandidateList candidates={result.candidates} empty="No pressing matches these answers. Start over and skip the uncertain ones." />
        </Section>
      )}
    </main>
  );
}
