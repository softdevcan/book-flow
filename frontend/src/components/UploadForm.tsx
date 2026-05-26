import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../api";
import type { LangDetection, LangOption } from "../types";

interface Props {
  onUploaded: () => void;
}

async function readExcerpt(file: File): Promise<string> {
  const blob = file.slice(0, 8192);
  return await blob.text();
}

export function UploadForm({ onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [styleGuide, setStyleGuide] = useState("");
  const [maxChars, setMaxChars] = useState(2000);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const [languages, setLanguages] = useState<LangOption[]>([]);
  const [sourceLang, setSourceLang] = useState<string>("");
  const [targetLang, setTargetLang] = useState<string>("");
  const [detection, setDetection] = useState<LangDetection | null>(null);
  const [detecting, setDetecting] = useState(false);

  useEffect(() => {
    api
      .listLanguages()
      .then((opts) => setLanguages(opts))
      .catch(() => setLanguages([]));
  }, []);

  async function handleFileChange(picked: File | null) {
    setFile(picked);
    setDetection(null);
    if (!picked) return;
    setDetecting(true);
    try {
      const excerpt = await readExcerpt(picked);
      if (excerpt.trim().length < 20) {
        setDetecting(false);
        return;
      }
      const det = await api.detectLanguage(excerpt);
      setDetection(det);
      setSourceLang((prev) => prev || det.code);
    } catch {
      // detection is best-effort
    } finally {
      setDetecting(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setMsg({ kind: "err", text: "Please choose a file" });
      return;
    }
    if (!targetLang) {
      setMsg({ kind: "err", text: "Pick a target language" });
      return;
    }
    if (sourceLang && sourceLang === targetLang) {
      setMsg({ kind: "err", text: "Source and target language must differ" });
      return;
    }
    const form = new FormData();
    form.append("file", file);
    if (title) form.append("title", title);
    if (author) form.append("author", author);
    if (styleGuide) form.append("style_guide", styleGuide);
    if (sourceLang) form.append("source_language", sourceLang);
    form.append("target_language", targetLang);
    form.append("max_chars", String(maxChars));

    setBusy(true);
    setMsg(null);
    try {
      const book = await api.uploadBook(form);
      const successMsg = `Uploaded "${book.title}" — ${book.total_chunks} chunks ready.`;
      setMsg({ kind: "ok", text: successMsg });
      toast.success(successMsg);
      setFile(null);
      setTitle("");
      setAuthor("");
      setStyleGuide("");
      setSourceLang("");
      setTargetLang("");
      setDetection(null);
      onUploaded();
    } catch (e) {
      const errMsg = String(e);
      setMsg({ kind: "err", text: errMsg });
      toast.error(`Upload failed: ${errMsg}`);
    } finally {
      setBusy(false);
    }
  }

  const detectionLabel = (() => {
    if (detecting) return "Detecting language…";
    if (!detection) return null;
    const langName =
      languages.find((l) => l.code === detection.code)?.name ?? detection.code.toUpperCase();
    if (detection.method === "lib") {
      return `Detected: ${langName} (lib, ${detection.confidence.toFixed(2)})`;
    }
    return `Detected: ${langName} (llm fallback)`;
  })();

  return (
    <form
      onSubmit={submit}
      className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 space-y-3"
    >
      <h2 className="font-semibold text-slate-800 dark:text-slate-100">Upload a book</h2>
      <p className="text-xs text-slate-500 dark:text-slate-400 -mt-2">
        Accepted: .epub, .pdf, .docx, .txt, .md (max 50 MB)
      </p>

      <input
        type="file"
        accept=".epub,.pdf,.docx,.txt,.md"
        onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
        className="block w-full text-sm text-slate-700 dark:text-slate-300 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-indigo-50 dark:file:bg-indigo-900/30 file:text-indigo-700 dark:file:text-indigo-300 hover:file:bg-indigo-100 dark:hover:file:bg-indigo-900/50"
      />

      <div className="grid grid-cols-2 gap-3">
        <Field label="Source language">
          <select
            value={sourceLang}
            onChange={(e) => setSourceLang(e.target.value)}
            className="input-dark"
          >
            <option value="">Auto-detect</option>
            {languages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name} ({l.code.toUpperCase()})
              </option>
            ))}
          </select>
          {detectionLabel && (
            <span className="block text-xs text-slate-500 dark:text-slate-400 mt-1">{detectionLabel}</span>
          )}
        </Field>
        <Field label="Target language">
          <select
            value={targetLang}
            onChange={(e) => setTargetLang(e.target.value)}
            required
            className="input-dark"
          >
            <option value="">Select…</option>
            {languages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name} ({l.code.toUpperCase()})
              </option>
            ))}
          </select>
        </Field>
      </div>

      <Field label="Title (optional)">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Auto-detected from file metadata"
          className="input-dark"
        />
      </Field>
      <Field label="Author (optional)">
        <input
          value={author}
          onChange={(e) => setAuthor(e.target.value)}
          className="input-dark"
        />
      </Field>
      <Field label="Style guide (optional)">
        <textarea
          value={styleGuide}
          onChange={(e) => setStyleGuide(e.target.value)}
          rows={3}
          placeholder="Genre: Cyberpunk Sci-Fi. Tone is gritty…"
          className="input-dark"
        />
      </Field>
      <Field label={`Chunk size: ~${maxChars} chars`}>
        <input
          type="range"
          min={500}
          max={4000}
          step={100}
          value={maxChars}
          onChange={(e) => setMaxChars(parseInt(e.target.value))}
          className="w-full accent-indigo-600"
        />
      </Field>

      <button
        disabled={busy}
        className="w-full bg-indigo-600 text-white rounded py-2 text-sm font-medium hover:bg-indigo-700 disabled:opacity-60"
      >
        {busy ? "Uploading…" : "Upload & chunk"}
      </button>

      {msg && (
        <div
          className={`text-sm rounded px-3 py-2 ${
            msg.kind === "ok"
              ? "bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800"
              : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800"
          }`}
        >
          {msg.text}
        </div>
      )}

      <style>{`
        .input-dark {
          width: 100%;
          border: 1px solid rgb(226 232 240);
          border-radius: 6px;
          padding: 6px 10px;
          font-size: 14px;
          background: white;
          color: rgb(15 23 42);
        }
        .dark .input-dark {
          border-color: rgb(71 85 105);
          background: rgb(30 41 59);
          color: rgb(226 232 240);
        }
        .input-dark:focus { outline: 2px solid rgb(99 102 241); outline-offset: -1px; }
      `}</style>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">{label}</span>
      {children}
    </label>
  );
}
