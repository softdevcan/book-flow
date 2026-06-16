// TODO: add collapsible source text toggle for long chunks
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "../api";
import type { Book, Chunk, ChunkStatus, TranslationVersion } from "../types";
import { VersionDiffModal } from "./VersionDiffModal";

interface Props {
  chunk: Chunk;
  book: Book;
  onTranslate: () => void;
  onUpdate: (patch: Partial<Chunk>) => void;
  /** Called with the refreshed chunk after a version is activated. */
  onChunkReplaced?: (chunk: Chunk) => void;
  /** False when no model is selected yet (two-stage needs both stages). */
  canTranslate?: boolean;
  /** Whether this card has keyboard focus (j/k navigation). */
  focused?: boolean;
  /** Trigger edit mode externally (keyboard shortcut `e`). */
  requestEdit?: boolean;
  onEditHandled?: () => void;
}

/*
1
2
3
4
5
*/

const statusStyles: Record<ChunkStatus, string> = {
  raw: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  in_review: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300",
  approved: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
};

export function ChunkCard({
  chunk,
  book,
  onTranslate,
  onUpdate,
  onChunkReplaced,
  canTranslate = true,
  focused = false,
  requestEdit = false,
  onEditHandled,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(chunk.translated_text ?? "");
  const [versions, setVersions] = useState<TranslationVersion[] | null>(null);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [diffModal, setDiffModal] = useState<{ active: TranslationVersion; other: TranslationVersion } | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync draft when chunk text changes externally (SSE update)
  useEffect(() => {
    if (!editing) setDraft(chunk.translated_text ?? "");
  }, [chunk.translated_text, editing]);

  // Handle external `e` keypress → open edit mode
  useEffect(() => {
    if (requestEdit && !editing && chunk.translated_text) {
      setDraft(chunk.translated_text);
      setEditing(true);
      onEditHandled?.();
    }
  }, [requestEdit]);

  // Focus textarea when edit mode opens
  useEffect(() => {
    if (editing) textareaRef.current?.focus();
  }, [editing]);

  const isFailed = chunk.editor_notes?.some(
    (n) => n.startsWith("translation_failed") || n.startsWith("stage1_failed") || n.startsWith("stage2_failed")
  );

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
    toast.success(`Version activated for chunk #${chunk.sequence_number}`);
    await loadVersions();
  }

  function openDiff(other: TranslationVersion) {
    if (!versions) return;
    const active = versions.find((v) => v.id === chunk.active_version_id);
    if (!active) return;
    setDiffModal({ active, other });
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
    <>
      <article
        data-chunk-id={chunk.id}
        className={`rounded-lg border bg-white dark:bg-slate-900 overflow-hidden transition-shadow ${
          focused
            ? "border-indigo-400 dark:border-indigo-500 ring-2 ring-indigo-300 dark:ring-indigo-700"
            : "border-slate-200 dark:border-slate-700"
        }`}
      >
        <header className="flex items-center justify-between px-4 py-2 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/60">
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
              #{chunk.sequence_number}
            </span>
            <span className={`text-xs rounded-full px-2 py-0.5 font-medium ${statusStyles[chunk.status]}`}>
              {chunk.status}
            </span>
            {isFailed && (
              <span className="text-xs rounded-full px-2 py-0.5 font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300">
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

        <div className="grid md:grid-cols-2 divide-x divide-slate-100 dark:divide-slate-800">
          {/* Source */}
          <div className="p-4">
            <p className="text-xs uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1">
              Source ({book.source_language.toUpperCase()})
            </p>
            <p className="text-sm whitespace-pre-wrap font-serif leading-relaxed text-slate-800 dark:text-slate-200">
              {chunk.source_text}
            </p>
          </div>

          {/* Translation */}
          <div className="p-4 bg-slate-50/40 dark:bg-slate-800/20">
            <div className="flex justify-between items-center mb-1">
              <p className="text-xs uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Translation ({book.target_language.toUpperCase()})
              </p>
              {chunk.translated_text && !editing && (
                <button
                  onClick={() => { setDraft(chunk.translated_text ?? ""); setEditing(true); }}
                  className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                >
                  Edit
                </button>
              )}
            </div>

            {editing ? (
              <div>
                <textarea
                  ref={textareaRef}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={8}
                  className="w-full text-sm font-serif border border-slate-300 dark:border-slate-600 rounded p-2 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                />
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => { onUpdate({ translated_text: draft }); setEditing(false); }}
                    className="text-xs bg-indigo-600 text-white rounded px-2 py-1 hover:bg-indigo-700"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditing(false)}
                    className="text-xs text-slate-500 dark:text-slate-400"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : chunk.translated_text ? (
              <p className="text-sm whitespace-pre-wrap font-serif leading-relaxed text-slate-800 dark:text-slate-200">
                {chunk.translated_text}
              </p>
            ) : (
              <p className="text-sm text-slate-400 dark:text-slate-500 italic">Not translated yet.</p>
            )}

            {chunk.editor_notes && chunk.editor_notes.length > 0 && (
              <details className="mt-3">
                <summary className="text-xs text-slate-500 dark:text-slate-400 cursor-pointer">
                  Editor notes ({chunk.editor_notes.length})
                </summary>
                <ul className="mt-1 space-y-1 text-xs text-slate-600 dark:text-slate-400 list-disc list-inside">
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
                <summary className="text-xs text-slate-500 dark:text-slate-400 cursor-pointer">
                  Versions{versions ? ` (${versions.length})` : ""}
                </summary>
                {versionsLoading && (
                  <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">Loading…</p>
                )}
                {versions && versions.length > 0 && (
                  <ul className="mt-2 space-y-2">
                    {versions.map((v) => {
                      const isActive = v.id === chunk.active_version_id;
                      return (
                        <li
                          key={v.id}
                          className={`rounded border p-2 text-xs ${
                            isActive
                              ? "border-indigo-300 dark:border-indigo-600 bg-indigo-50 dark:bg-indigo-900/20"
                              : "border-slate-200 dark:border-slate-700"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2 flex-wrap">
                            <span className="text-slate-500 dark:text-slate-400">
                              {versionLabel(v)} · {fmtTime(v.created_at)}
                            </span>
                            <div className="flex items-center gap-2">
                              {!isActive && (
                                <button
                                  onClick={() => openDiff(v)}
                                  className="text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 hover:underline"
                                >
                                  Compare
                                </button>
                              )}
                              {isActive ? (
                                <span className="rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 px-2 py-0.5 font-medium">
                                  active
                                </span>
                              ) : (
                                <button
                                  onClick={() => useVersion(v.id)}
                                  className="text-indigo-600 dark:text-indigo-400 hover:underline"
                                >
                                  Use this
                                </button>
                              )}
                            </div>
                          </div>
                          <p className="mt-1 text-slate-600 dark:text-slate-400 font-serif line-clamp-3 whitespace-pre-wrap">
                            {v.translated_text}
                          </p>
                        </li>
                      );
                    })}
                  </ul>
                )}
                {versions && versions.length === 0 && (
                  <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">No versions yet.</p>
                )}
              </details>
            )}
          </div>
        </div>
      </article>

      {diffModal && (
        <VersionDiffModal
          activeVersion={diffModal.active}
          otherVersion={diffModal.other}
          onClose={() => setDiffModal(null)}
          onUse={useVersion}
        />
      )}
    </>
  );
}
