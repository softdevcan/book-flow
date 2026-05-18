import { useState } from "react";
import { api } from "../api";

interface Props {
  onUploaded: () => void;
}

export function UploadForm({ onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [styleGuide, setStyleGuide] = useState("");
  const [maxChars, setMaxChars] = useState(2000);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setMsg({ kind: "err", text: "Please choose a file" });
      return;
    }
    const form = new FormData();
    form.append("file", file);
    if (title) form.append("title", title);
    if (author) form.append("author", author);
    if (styleGuide) form.append("style_guide", styleGuide);
    form.append("max_chars", String(maxChars));

    setBusy(true);
    setMsg(null);
    try {
      const book = await api.uploadBook(form);
      setMsg({
        kind: "ok",
        text: `Uploaded "${book.title}" — ${book.total_chunks} chunks ready.`,
      });
      setFile(null);
      setTitle("");
      setAuthor("");
      setStyleGuide("");
      onUploaded();
    } catch (e) {
      setMsg({ kind: "err", text: String(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="rounded-lg border border-slate-200 bg-white p-5 space-y-3"
    >
      <h2 className="font-semibold">Upload a book</h2>
      <p className="text-xs text-slate-500 -mt-2">
        Accepted: .epub, .pdf, .docx, .txt, .md (max 50 MB)
      </p>

      <input
        type="file"
        accept=".epub,.pdf,.docx,.txt,.md"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="block w-full text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
      />

      <Field label="Title (optional)">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Auto-detected from file metadata"
          className="input"
        />
      </Field>
      <Field label="Author (optional)">
        <input
          value={author}
          onChange={(e) => setAuthor(e.target.value)}
          className="input"
        />
      </Field>
      <Field label="Style guide (optional)">
        <textarea
          value={styleGuide}
          onChange={(e) => setStyleGuide(e.target.value)}
          rows={3}
          placeholder="Genre: Cyberpunk Sci-Fi. Tone is gritty…"
          className="input"
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
          className="w-full"
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
              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
              : "bg-red-50 text-red-700 border border-red-200"
          }`}
        >
          {msg.text}
        </div>
      )}

      <style>{`
        .input {
          width: 100%;
          border: 1px solid rgb(226 232 240);
          border-radius: 6px;
          padding: 6px 10px;
          font-size: 14px;
          background: white;
        }
        .input:focus { outline: 2px solid rgb(99 102 241); outline-offset: -1px; }
      `}</style>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-slate-600 mb-1">{label}</span>
      {children}
    </label>
  );
}
