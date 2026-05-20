import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Book, Chunk } from "../types";
import { ModelPicker } from "./ModelPicker";
import { GlossaryPanel } from "./GlossaryPanel";
import { ChunkCard } from "./ChunkCard";
import { AnalyticsPage } from "./AnalyticsPage";

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
  a.download = `${book.title.replace(/\s+/g, "_")}_TR.txt`;
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

export function BookDetail({ bookId, onBack }: Props) {
  const [book, setBook] = useState<Book | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [translating, setTranslating] = useState(false);
  const [activeChapterIdx, setActiveChapterIdx] = useState(0);
  const [activeView, setActiveView] = useState<ActiveView>("chunks");
  const pollRef = useRef<number | null>(null);

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
    const anyRaw = chunks.some((c) => c.status === "raw" && c.translated_text === null);
    if (!anyRaw) {
      if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }
    if (pollRef.current) return;
    pollRef.current = window.setInterval(loadAll, 3000);
    return () => { if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; } };
  }, [chunks]);

  async function translateAll() {
    setTranslating(true);
    try {
      await api.translateBook(bookId, { model: selectedModel ?? undefined });
      loadAll();
    } finally {
      setTranslating(false);
    }
  }

  async function translateOne(id: number) {
    await api.translateChunk(id, { model: selectedModel ?? undefined });
    loadAll();
  }

  async function updateChunk(id: number, patch: Partial<Chunk>) {
    const updated = await api.updateChunk(id, patch);
    setChunks((prev) => prev.map((c) => (c.id === id ? updated : c)));
  }

  if (!book) return <p className="text-sm text-slate-500">Loading…</p>;

  const counts = chunks.reduce(
    (acc, c) => { acc[c.status]++; return acc; },
    { raw: 0, in_review: 0, approved: 0 } as Record<string, number>,
  );
  const translatedCount = chunks.filter((c) => c.translated_text).length;
  const progressPct = chunks.length ? Math.round((translatedCount / chunks.length) * 100) : 0;
  const pendingCount = counts.raw;

  const groups = groupByChapter(chunks);
  const safeIdx = Math.min(activeChapterIdx, groups.length - 1);
  const activeGroup = groups[safeIdx];

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex items-center gap-3 flex-wrap justify-between">
        <button onClick={onBack} className="text-sm text-indigo-600 hover:underline shrink-0">
          ← Back to library
        </button>
        <div className="flex items-center gap-3 flex-wrap">
          {activeView === "chunks" && (
            <>
              <ModelPicker selected={selectedModel} onChange={setSelectedModel} />
              <button
                onClick={translateAll}
                disabled={translating || pendingCount === 0}
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
                className="border border-slate-300 hover:border-slate-400 disabled:opacity-40 disabled:cursor-not-allowed text-slate-700 text-sm rounded px-3 py-1.5"
              >
                ↓ Export TXT
                {translatedCount > 0 && translatedCount < chunks.length && (
                  <span className="ml-1 text-xs text-amber-600">({translatedCount}/{chunks.length})</span>
                )}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Book title + stats */}
      <div>
        <h1 className="text-xl font-bold tracking-tight">{book.title}</h1>
        <p className="text-sm text-slate-500">
          {book.author ?? "Unknown author"} · {book.total_chunks} chunks ·{" "}
          <span className="text-amber-600">{counts.raw} untranslated</span> ·{" "}
          <span className="text-indigo-600">{counts.in_review} in review</span> ·{" "}
          <span className="text-emerald-600">{counts.approved} approved</span>
        </p>
        {chunks.length > 0 && (
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-slate-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="text-xs text-slate-500 shrink-0">{progressPct}%</span>
          </div>
        )}
      </div>

      {/* View tabs */}
      <div className="flex gap-1 border-b border-slate-200">
        {(["chunks", "analytics"] as ActiveView[]).map((view) => (
          <button
            key={view}
            onClick={() => setActiveView(view)}
            className={`px-4 py-2 text-sm font-medium rounded-t transition-colors ${
              activeView === view
                ? "bg-white border border-b-white border-slate-200 -mb-px text-indigo-700"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {view === "chunks" ? "Chunks" : "Analytics"}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      )}

      {/* Analytics view */}
      {activeView === "analytics" && (
        <AnalyticsPage book={book} chunks={chunks} />
      )}

      {/* Chunks view: sidebar + content */}
      {activeView === "chunks" && (
        <div className="flex gap-6 items-start">

          {/* Left sidebar: chapter list */}
          <nav className="w-56 shrink-0 rounded-lg border border-slate-200 bg-white overflow-hidden sticky top-4">
            <div className="px-3 py-2 border-b border-slate-100 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Chapters
            </div>
            <ul className="divide-y divide-slate-100 max-h-[70vh] overflow-y-auto">
              {groups.map((g, i) => {
                const st = chapterStatus(g);
                const isActive = i === safeIdx;
                return (
                  <li key={i}>
                    <button
                      onClick={() => setActiveChapterIdx(i)}
                      className={`w-full text-left px-3 py-2.5 flex items-start gap-2 hover:bg-slate-50 transition-colors ${isActive ? "bg-indigo-50 border-l-2 border-indigo-500" : ""}`}
                    >
                      <span className={`mt-0.5 shrink-0 w-2 h-2 rounded-full ${
                        st === "all_approved" ? "bg-emerald-400" :
                        st === "partial" ? "bg-indigo-400" :
                        "bg-amber-300"
                      }`} />
                      <div>
                        <div className={`text-sm leading-tight ${isActive ? "font-semibold text-indigo-700" : "text-slate-700"}`}>
                          {g.title}
                        </div>
                        <div className="text-xs text-slate-400 mt-0.5">
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
                    <h2 className="font-semibold text-slate-800">{activeGroup.title}</h2>
                    <span className="text-xs text-slate-500">
                      {activeGroup.chunks.filter((c) => c.translated_text).length}/{activeGroup.chunks.length} translated
                    </span>
                  </div>
                  {activeGroup.chunks.map((c) => (
                    <ChunkCard
                      key={c.id}
                      chunk={c}
                      onTranslate={() => translateOne(c.id)}
                      onUpdate={(patch) => updateChunk(c.id, patch)}
                    />
                  ))}
                </>
              )}
            </section>

            <aside className="w-72 shrink-0 space-y-4 sticky top-4">
              <GlossaryPanel bookId={bookId} />
              {book.style_guide && (
                <div className="rounded-lg border border-slate-200 bg-white p-4">
                  <h3 className="font-semibold mb-2 text-sm">Style guide</h3>
                  <p className="text-sm whitespace-pre-wrap text-slate-700">{book.style_guide}</p>
                </div>
              )}
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}
