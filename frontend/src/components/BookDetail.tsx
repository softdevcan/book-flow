import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "../api";
import type { Book, Chunk } from "../types";
import { ModelPicker } from "./ModelPicker";
import { GlossaryPanel } from "./GlossaryPanel";
import { ChunkCard } from "./ChunkCard";
import { AnalyticsPage } from "./AnalyticsPage";
import { BatchProgressBar } from "./BatchProgressBar";
import { ChunkFilterBar, type StatusFilter } from "./ChunkFilterBar";
import { useChunkEvents, type ChunkEvent } from "../hooks/useChunkEvents";
import { useChunkKeybindings } from "../hooks/useChunkKeybindings";

type ActiveView = "chunks" | "analytics";

interface Props {
  bookId: number;
  onBack: () => void;
}

interface ChapterGroup {
  title: string;
  chunks: Chunk[];
}

function groupByChapter(chunks: Chunk[]): ChapterGroup[] {
  const groups: ChapterGroup[] = [];
  let current: ChapterGroup = { title: "Introduction", chunks: [] };

  for (const chunk of chunks) {
    const lines = chunk.source_text.trim().split("\n");
    const firstLine = lines[0].trim();
    const isHeading =
      /^(chapter|bölüm|part|kısım|section|prologue|epilogue|prolog|epilog|önsöz|giriş|sonuç)\b/i.test(
        firstLine
      ) && firstLine.length <= 80 && !firstLine.includes(".");

    if (isHeading) {
      if (current.chunks.length > 0) groups.push(current);
      current = { title: firstLine, chunks: [chunk] };
    } else {
      current.chunks.push(chunk);
    }
  }
  if (current.chunks.length > 0) groups.push(current);
  return groups;
}

function exportAsTxt(book: Book, chunks: Chunk[]) {
  const lines: string[] = [book.title];
  if (book.author) lines.push(book.author);
  lines.push("=".repeat(60), "");
  for (const c of chunks) {
    if (c.translated_text) {
      lines.push(c.translated_text, "");
    }
  }
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${book.title.replace(/\s+/g, "_")}_${book.target_language.toUpperCase()}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

function chapterStatus(group: ChapterGroup): "all_approved" | "partial" | "untranslated" {
  const total = group.chunks.length;
  const approved = group.chunks.filter((c) => c.status === "approved").length;
  const translated = group.chunks.filter((c) => c.translated_text).length;
  if (approved === total) return "all_approved";
  if (translated > 0) return "partial";
  return "untranslated";
}

// Coalesce rapid SSE toasts: if > 5 events in 2s, collapse to one summary.
function makeToastCoalescer() {
  let buffer: string[] = [];
  let timer: number | null = null;
  return function push(msg: string) {
    buffer.push(msg);
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      if (buffer.length > 5) {
        toast.success(`${buffer.length} chunks translated`);
      } else {
        buffer.forEach((m) => toast.success(m));
      }
      buffer = [];
      timer = null;
    }, 2000);
  };
}

const toastSuccess = makeToastCoalescer();

export function BookDetail({ bookId, onBack }: Props) {
  const [book, setBook] = useState<Book | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [stage1Model, setStage1Model] = useState<string | null>(null);
  const [stage2Model, setStage2Model] = useState<string | null>(null);
  const [pipeline, setPipeline] = useState<"single" | "two_stage">("single");
  const [stageDefaults, setStageDefaults] = useState<{ stage1: string; stage2: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [translating, setTranslating] = useState(false);
  const [activeChapterIdx, setActiveChapterIdx] = useState(0);
  const [activeView, setActiveView] = useState<ActiveView>("chunks");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [searchText, setSearchText] = useState("");
  const [focusedChunkId, setFocusedChunkId] = useState<number | null>(null);
  const [editRequestId, setEditRequestId] = useState<number | null>(null);
  const [showHelp, setShowHelp] = useState(false);
  const [lastBatchEvent, setLastBatchEvent] = useState<ChunkEvent | null>(null);
  const pollRef = useRef<number | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  async function loadAll() {
    try {
      const [b, c] = await Promise.all([api.getBook(bookId), api.listChunks(bookId)]);
      setBook(b);
      setChunks(c);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => { loadAll(); }, [bookId]);

  useEffect(() => {
    api.listModels()
      .then((res) => {
        setPipeline(res.pipeline);
        setStageDefaults(res.stage_defaults);
      })
      .catch(() => setStageDefaults(null));
  }, []);

  // Fallback 3-second poll when SSE is closed and chunks are still pending.
  useEffect(() => {
    const anyRaw = chunks.some((c) => c.status === "raw" && c.translated_text === null);
    if (!anyRaw) {
      if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }
    if (pollRef.current) return;
    pollRef.current = window.setInterval(loadAll, 3000);
    return () => { if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; } };
  }, [chunks]);

  // SSE event handler
  const handleChunkEvent = useCallback((e: ChunkEvent) => {
    if (e.type === "batch_progress") {
      setLastBatchEvent(e);
      return;
    }
    if (e.type === "chunk_updated" && e.chunk_id != null) {
      // Fetch the updated chunk and replace in state.
      api.getChunk(e.chunk_id).then((updated) => {
        setChunks((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
        if (e.translated) {
          toastSuccess(`#${updated.sequence_number} translated`);
        }
      }).catch(() => {});
    }
    if (e.type === "chunk_failed" && e.chunk_id != null) {
      toast.error(`Chunk #${e.chunk_id} failed — ${e.reason ?? "unknown error"}`);
      api.getChunk(e.chunk_id).then((updated) => {
        setChunks((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      }).catch(() => {});
    }
  }, []);

  useChunkEvents(bookId, handleChunkEvent, activeView === "chunks");

  const effStage1 = stage1Model ?? (stageDefaults?.stage1 || null);
  const effStage2 = stage2Model ?? (stageDefaults?.stage2 || null);
  const modelsReady = pipeline === "single" ? true : Boolean(effStage1 && effStage2);

  const translateOverrides = () =>
    pipeline === "two_stage"
      ? { stage1_model: stage1Model ?? undefined, stage2_model: stage2Model ?? undefined }
      : { model: stage1Model ?? undefined };

  async function translateAll() {
    setTranslating(true);
    try {
      await api.translateBook(bookId, translateOverrides());
      toast.success("Translation queued for all pending chunks");
      loadAll();
    } catch (e) {
      toast.error(`Queue failed: ${e}`);
    } finally {
      setTranslating(false);
    }
  }

  async function translateOne(id: number) {
    const chunk = chunks.find((c) => c.id === id);
    const seqNo = chunk?.sequence_number ?? id;
    toast.promise(api.translateChunk(id, translateOverrides()), {
      loading: `Queuing #${seqNo}…`,
      success: `Queued #${seqNo}`,
      error: (e) => `Queue failed: ${e}`,
    });
    loadAll();
  }

  async function updateChunk(id: number, patch: Partial<Chunk>) {
    const updated = await api.updateChunk(id, patch);
    setChunks((prev) => prev.map((c) => (c.id === id ? updated : c)));
  }

  function replaceChunk(updated: Chunk) {
    setChunks((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  }

  // ---- Keyboard shortcuts ----
  const groups = book ? groupByChapter(chunks) : [];
  const safeIdx = Math.min(activeChapterIdx, Math.max(0, groups.length - 1));
  const activeGroup = groups[safeIdx];

  // Filtered chunks in active chapter
  function applyFilters(chks: Chunk[]): Chunk[] {
    let result = chks;
    if (statusFilter !== "all") {
      if (statusFilter === "failed") {
        result = result.filter((c) =>
          c.editor_notes?.some((n) =>
            n.startsWith("translation_failed") || n.startsWith("stage1_failed") || n.startsWith("stage2_failed")
          )
        );
      } else {
        result = result.filter((c) => c.status === statusFilter);
      }
    }
    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      result = result.filter(
        (c) =>
          c.source_text.toLowerCase().includes(q) ||
          (c.translated_text?.toLowerCase().includes(q) ?? false)
      );
    }
    return result;
  }

  const visibleChunks = activeGroup ? applyFilters(activeGroup.chunks) : [];
  const visibleChunkIds = visibleChunks.map((c) => c.id);

  useChunkKeybindings({
    enabled: activeView === "chunks",
    chunkIds: visibleChunkIds,
    focusedChunkId,
    onFocus: setFocusedChunkId,
    onTranslate: (id) => translateOne(id),
    onApprove: (id) => updateChunk(id, { status: "approved" }),
    onEdit: (id) => setEditRequestId(id),
    onFocusSearch: () => searchInputRef.current?.focus(),
    onHelp: () => setShowHelp((v) => !v),
  });

  if (!book) return <p className="text-sm text-slate-500 dark:text-slate-400">Loading…</p>;

  const counts = chunks.reduce(
    (acc, c) => { acc[c.status]++; return acc; },
    { raw: 0, in_review: 0, approved: 0 } as Record<string, number>,
  );

  // Counts for filter chips (total in chapter, not in current filter)
  const chapterCounts: Record<StatusFilter, number> = {
    all: activeGroup?.chunks.length ?? 0,
    raw: activeGroup?.chunks.filter((c) => c.status === "raw").length ?? 0,
    in_review: activeGroup?.chunks.filter((c) => c.status === "in_review").length ?? 0,
    approved: activeGroup?.chunks.filter((c) => c.status === "approved").length ?? 0,
    failed: activeGroup?.chunks.filter((c) =>
      c.editor_notes?.some((n) =>
        n.startsWith("translation_failed") || n.startsWith("stage1_failed") || n.startsWith("stage2_failed")
      )
    ).length ?? 0,
  };

  const translatedCount = chunks.filter((c) => c.translated_text).length;
  const progressPct = chunks.length ? Math.round((translatedCount / chunks.length) * 100) : 0;
  const pendingCount = counts.raw;

  return (
    <div className="space-y-4">
      {/* Sticky batch progress bar */}
      <BatchProgressBar
        totalChunks={chunks.length}
        translatedChunks={translatedCount}
        lastBatchEvent={lastBatchEvent}
      />

      {/* Top bar */}
      <div className="flex items-center gap-3 flex-wrap justify-between">
        <button onClick={onBack} className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline shrink-0">
          ← Back to library
        </button>
        <div className="flex items-center gap-3 flex-wrap">
          {activeView === "chunks" && (
            <>
              {pipeline === "two_stage" ? (
                <>
                  <ModelPicker label="Stage 1 (Builder)" selected={stage1Model} onChange={setStage1Model} defaultModel={stageDefaults?.stage1} />
                  <ModelPicker label="Stage 2 (Artist)" selected={stage2Model} onChange={setStage2Model} defaultModel={stageDefaults?.stage2} />
                </>
              ) : (
                <ModelPicker label="Model" selected={stage1Model} onChange={setStage1Model} />
              )}
              <button
                onClick={translateAll}
                disabled={translating || pendingCount === 0 || !modelsReady}
                title={!modelsReady ? "Select a model for both Stage 1 and Stage 2 first" : undefined}
                className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded px-3 py-1.5 flex items-center gap-1.5"
              >
                {translating && (
                  <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                )}
                {translating ? "Queuing…" : pendingCount > 0 ? `Translate ${pendingCount} pending` : "All translated"}
              </button>
              <button
                onClick={() => exportAsTxt(book, chunks)}
                disabled={translatedCount === 0}
                title={translatedCount === 0 ? "No translations yet" : `Export ${translatedCount}/${chunks.length} chunks`}
                className="border border-slate-300 dark:border-slate-600 hover:border-slate-400 dark:hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed text-slate-700 dark:text-slate-300 text-sm rounded px-3 py-1.5"
              >
                ↓ Export TXT
                {translatedCount > 0 && translatedCount < chunks.length && (
                  <span className="ml-1 text-xs text-amber-600 dark:text-amber-400">({translatedCount}/{chunks.length})</span>
                )}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Book title + stats */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          {book.title}{" "}
          <span className="ml-2 align-middle text-xs font-medium text-slate-500 dark:text-slate-400 rounded bg-slate-100 dark:bg-slate-800 px-2 py-0.5">
            {book.source_language.toUpperCase()} → {book.target_language.toUpperCase()}
          </span>
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {book.author ?? "Unknown author"} · {book.total_chunks} chunks ·{" "}
          <span className="text-amber-600 dark:text-amber-400">{counts.raw} untranslated</span> ·{" "}
          <span className="text-indigo-600 dark:text-indigo-400">{counts.in_review} in review</span> ·{" "}
          <span className="text-emerald-600 dark:text-emerald-400">{counts.approved} approved</span>
        </p>
        {chunks.length > 0 && (
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div className="h-full bg-indigo-500 rounded-full transition-all duration-500" style={{ width: `${progressPct}%` }} />
            </div>
            <span className="text-xs text-slate-500 dark:text-slate-400 shrink-0">{progressPct}%</span>
          </div>
        )}
      </div>

      {/* View tabs */}
      <div className="flex gap-1 border-b border-slate-200 dark:border-slate-700">
        {(["chunks", "analytics"] as ActiveView[]).map((view) => (
          <button
            key={view}
            onClick={() => setActiveView(view)}
            className={`px-4 py-2 text-sm font-medium rounded-t transition-colors ${
              activeView === view
                ? "bg-white dark:bg-slate-900 border border-b-white dark:border-b-slate-900 border-slate-200 dark:border-slate-700 -mb-px text-indigo-700 dark:text-indigo-400"
                : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
            }`}
          >
            {view === "chunks" ? "Chunks" : "Analytics"}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-700 dark:text-red-400">{error}</div>
      )}

      {activeView === "analytics" && <AnalyticsPage book={book} chunks={chunks} />}

      {activeView === "chunks" && (
        <div className="flex gap-6 items-start">
          {/* Left sidebar: chapter list */}
          <nav className="w-56 shrink-0 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 overflow-hidden sticky top-4">
            <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-800 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Chapters
            </div>
            <ul className="divide-y divide-slate-100 dark:divide-slate-800 max-h-[70vh] overflow-y-auto">
              {groups.map((g, i) => {
                const st = chapterStatus(g);
                const isActive = i === safeIdx;
                return (
                  <li key={i}>
                    <button
                      onClick={() => setActiveChapterIdx(i)}
                      className={`w-full text-left px-3 py-2.5 flex items-start gap-2 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${isActive ? "bg-indigo-50 dark:bg-indigo-900/20 border-l-2 border-indigo-500" : ""}`}
                    >
                      <span className={`mt-0.5 shrink-0 w-2 h-2 rounded-full ${
                        st === "all_approved" ? "bg-emerald-400" :
                        st === "partial" ? "bg-indigo-400" :
                        "bg-amber-300"
                      }`} />
                      <div>
                        <div className={`text-sm leading-tight ${isActive ? "font-semibold text-indigo-700 dark:text-indigo-300" : "text-slate-700 dark:text-slate-300"}`}>
                          {g.title}
                        </div>
                        <div className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                          {g.chunks.length} chunk{g.chunks.length !== 1 ? "s" : ""}
                        </div>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>

          {/* Right: active chapter chunks + glossary */}
          <div className="flex-1 min-w-0 flex gap-6 items-start">
            <section className="flex-1 min-w-0 space-y-4">
              {activeGroup && (
                <>
                  <div className="flex items-center justify-between">
                    <h2 className="font-semibold text-slate-800 dark:text-slate-100">{activeGroup.title}</h2>
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      {activeGroup.chunks.filter((c) => c.translated_text).length}/{activeGroup.chunks.length} translated
                    </span>
                  </div>

                  {/* Filter bar */}
                  <ChunkFilterBar
                    statusFilter={statusFilter}
                    searchText={searchText}
                    onStatusChange={setStatusFilter}
                    onSearchChange={setSearchText}
                    counts={chapterCounts}
                    searchInputRef={searchInputRef as React.RefObject<HTMLInputElement | null>}
                  />

                  {visibleChunks.length === 0 && (
                    <p className="text-sm text-slate-400 dark:text-slate-500 italic py-4 text-center">
                      No chunks match the current filter.
                    </p>
                  )}

                  {visibleChunks.map((c) => (
                    <ChunkCard
                      key={c.id}
                      chunk={c}
                      book={book}
                      canTranslate={modelsReady}
                      focused={focusedChunkId === c.id}
                      requestEdit={editRequestId === c.id}
                      onEditHandled={() => setEditRequestId(null)}
                      onTranslate={() => translateOne(c.id)}
                      onUpdate={(patch) => updateChunk(c.id, patch)}
                      onChunkReplaced={replaceChunk}
                    />
                  ))}
                </>
              )}
            </section>

            <aside className="w-72 shrink-0 space-y-4 sticky top-4">
              <GlossaryPanel bookId={bookId} />
              {book.style_guide && (
                <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4">
                  <h3 className="font-semibold mb-2 text-sm text-slate-800 dark:text-slate-100">Style guide</h3>
                  <p className="text-sm whitespace-pre-wrap text-slate-700 dark:text-slate-300">{book.style_guide}</p>
                </div>
              )}
            </aside>
          </div>
        </div>
      )}

      {/* Keyboard shortcuts help overlay */}
      {showHelp && (
        <div
          className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
          onClick={() => setShowHelp(false)}
        >
          <div
            className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl p-6 max-w-sm w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">Keyboard shortcuts</h2>
            <table className="w-full text-sm">
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {[
                  ["j / k", "Next / previous chunk"],
                  ["t", "Translate focused chunk"],
                  ["a", "Approve focused chunk"],
                  ["e", "Edit focused chunk"],
                  ["/", "Focus search bar"],
                  ["?", "Toggle this help"],
                ].map(([key, desc]) => (
                  <tr key={key}>
                    <td className="py-1.5 pr-4">
                      <kbd className="font-mono text-xs bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded px-1.5 py-0.5">{key}</kbd>
                    </td>
                    <td className="py-1.5 text-slate-600 dark:text-slate-400">{desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button
              onClick={() => setShowHelp(false)}
              className="mt-4 text-xs text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300"
            >
              Close (Esc or ?)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
