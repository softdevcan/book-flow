import { useState } from "react";
import { api } from "../api";
import type { Book, Chunk, ChunkStatus, TranslationVersion } from "../types";

interface Props {
  chunk: Chunk;
  book: Book;
  onTranslate: () => void;
  onUpdate: (patch: Partial<Chunk>) => void;
  /** Called with the refreshed chunk after a version is activated. */
  onChunkReplaced?: (chunk: Chunk) => void;
  /** False when no model is selected yet (two-stage needs both stages). */
  canTranslate?: boolean;
  /** Whether this chunk is currently in the multi-select set. */
  selected?: boolean;
  /** Toggle selection; omit to hide the checkbox entirely. */
  onToggleSelect?: () => void;
}

const statusStyles: Record<ChunkStatus, string> = {
  raw: "bg-amber-100 text-amber-800",
  in_review: "bg-indigo-100 text-indigo-800",
  approved: "bg-emerald-100 text-emerald-800",
};

export function ChunkCard({
  chunk,
  book,
  onTranslate,
  onUpdate,
  onChunkReplaced,
  canTranslate = true,
  selected = false,
  onToggleSelect,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(chunk.translated_text ?? "");
  const [versions, setVersions] = useState<TranslationVersion[] | null>(null);
  const [versionsLoading, setVersionsLoading] = useState(false);

  const isFailed = chunk.editor_notes?.some((n) => n.startsWith("translation_failed"));

  async function loadVersions() {
    setVersionsLoading(true);
    try {
      setVersions(await api.listVersions(chunk.id));
    } finally {
      setVersionsLoading(false);
    }
  }

  async function useVersion(versionId: number) {
    const updated = await api.activateVersion(chunk.id, versionId);
    onChunkReplaced?.(updated);
    await loadVersions(); // refresh active badge
  }

  function fmtTime(iso: string) {
    const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    return d.toLocaleString();
  }

  function versionLabel(v: TranslationVersion) {
    if (v.pipeline === "two_stage") {
      return `two-stage · ${v.stage1_model ?? "?"} → ${v.stage2_model ?? "?"}`;
    }
    return `${v.pipeline ?? "single"} · ${v.stage1_model ?? "?"}`;
  }

  return (
    <article
      className={`rounded-lg border bg-white overflow-hidden transition-colors ${
        selected ? "border-indigo-400 ring-1 ring-indigo-200" : "border-slate-200"
      }`}
    >
      <header className="flex items-center justify-between px-4 py-2 border-b border-slate-100 bg-slate-50">
        <div className="flex items-center gap-3">
          {onToggleSelect && (
            <input
              type="checkbox"
              checked={selected}
              onChange={onToggleSelect}
              aria-label={`Select chunk ${chunk.sequence_number}`}
              className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
            />
          )}
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
            disabled={!canTranslate}
            title={!canTranslate ? "Select a model first" : undefined}
            className="text-xs bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded px-2 py-1"
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
            Source ({book.source_language.toUpperCase()})
          </p>
          <p className="text-sm whitespace-pre-wrap font-serif leading-relaxed">
            {chunk.source_text}
          </p>
        </div>
        <div className="p-4 bg-slate-50/40">
          <div className="flex justify-between items-center mb-1">
            <p className="text-xs uppercase tracking-wider text-slate-400">
              Translation ({book.target_language.toUpperCase()})
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

          {chunk.translated_text && (
            <details
              className="mt-2"
              onToggle={(e) => {
                if ((e.target as HTMLDetailsElement).open && versions === null) {
                  loadVersions();
                }
              }}
            >
              <summary className="text-xs text-slate-500 cursor-pointer">
                Versions{versions ? ` (${versions.length})` : ""}
              </summary>
              {versionsLoading && (
                <p className="mt-1 text-xs text-slate-400">Loading…</p>
              )}
              {versions && versions.length > 0 && (
                <ul className="mt-2 space-y-2">
                  {versions.map((v) => {
                    const isActive = v.id === chunk.active_version_id;
                    return (
                      <li
                        key={v.id}
                        className={`rounded border p-2 text-xs ${
                          isActive ? "border-indigo-300 bg-indigo-50" : "border-slate-200"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-slate-500">
                            {versionLabel(v)} · {fmtTime(v.created_at)}
                          </span>
                          {isActive ? (
                            <span className="rounded-full bg-indigo-100 text-indigo-700 px-2 py-0.5 font-medium">
                              active
                            </span>
                          ) : (
                            <button
                              onClick={() => useVersion(v.id)}
                              className="text-indigo-600 hover:underline"
                            >
                              Use this
                            </button>
                          )}
                        </div>
                        <p className="mt-1 text-slate-600 font-serif line-clamp-3 whitespace-pre-wrap">
                          {v.translated_text}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              )}
              {versions && versions.length === 0 && (
                <p className="mt-1 text-xs text-slate-400">No versions yet.</p>
              )}
            </details>
          )}
        </div>
      </div>
    </article>
  );
}
