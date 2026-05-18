import { useState } from "react";
import type { Chunk, ChunkStatus } from "../types";

interface Props {
  chunk: Chunk;
  onTranslate: () => void;
  onUpdate: (patch: Partial<Chunk>) => void;
}

const statusStyles: Record<ChunkStatus, string> = {
  raw: "bg-amber-100 text-amber-800",
  in_review: "bg-indigo-100 text-indigo-800",
  approved: "bg-emerald-100 text-emerald-800",
};

export function ChunkCard({ chunk, onTranslate, onUpdate }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(chunk.translated_text ?? "");

  const isFailed = chunk.editor_notes?.some((n) => n.startsWith("translation_failed"));

  return (
    <article className="rounded-lg border border-slate-200 bg-white overflow-hidden">
      <header className="flex items-center justify-between px-4 py-2 border-b border-slate-100 bg-slate-50">
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-500">
            #{chunk.sequence_number}
          </span>
          <span
            className={`text-xs rounded-full px-2 py-0.5 font-medium ${statusStyles[chunk.status]}`}
          >
            {chunk.status}
          </span>
          {isFailed && (
            <span className="text-xs rounded-full px-2 py-0.5 font-medium bg-red-100 text-red-700">
              failed
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onTranslate}
            className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded px-2 py-1"
          >
            {chunk.translated_text ? "Re-translate" : "Translate"}
          </button>
          {chunk.translated_text && chunk.status !== "approved" && (
            <button
              onClick={() => onUpdate({ status: "approved" })}
              className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white rounded px-2 py-1"
            >
              Approve
            </button>
          )}
        </div>
      </header>

      <div className="grid md:grid-cols-2 divide-x divide-slate-100">
        <div className="p-4">
          <p className="text-xs uppercase tracking-wider text-slate-400 mb-1">
            Source (EN)
          </p>
          <p className="text-sm whitespace-pre-wrap font-serif leading-relaxed">
            {chunk.source_text}
          </p>
        </div>
        <div className="p-4 bg-slate-50/40">
          <div className="flex justify-between items-center mb-1">
            <p className="text-xs uppercase tracking-wider text-slate-400">
              Translation (TR)
            </p>
            {chunk.translated_text && !editing && (
              <button
                onClick={() => {
                  setDraft(chunk.translated_text ?? "");
                  setEditing(true);
                }}
                className="text-xs text-indigo-600 hover:underline"
              >
                Edit
              </button>
            )}
          </div>

          {editing ? (
            <div>
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={8}
                className="w-full text-sm font-serif border border-slate-300 rounded p-2"
              />
              <div className="flex gap-2 mt-2">
                <button
                  onClick={() => {
                    onUpdate({ translated_text: draft });
                    setEditing(false);
                  }}
                  className="text-xs bg-indigo-600 text-white rounded px-2 py-1"
                >
                  Save
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="text-xs text-slate-500"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : chunk.translated_text ? (
            <p className="text-sm whitespace-pre-wrap font-serif leading-relaxed">
              {chunk.translated_text}
            </p>
          ) : (
            <p className="text-sm text-slate-400 italic">Not translated yet.</p>
          )}

          {chunk.editor_notes && chunk.editor_notes.length > 0 && (
            <details className="mt-3">
              <summary className="text-xs text-slate-500 cursor-pointer">
                Editor notes ({chunk.editor_notes.length})
              </summary>
              <ul className="mt-1 space-y-1 text-xs text-slate-600 list-disc list-inside">
                {chunk.editor_notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      </div>
    </article>
  );
}
