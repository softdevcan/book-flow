import type { Book, Chunk } from "../types";

interface Props {
  book: Book;
  chunks: Chunk[];
}

function wordCount(text: string): number {
  return text.trim() === "" ? 0 : text.trim().split(/\s+/).length;
}

function StatusBadge({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className={`rounded-lg border p-4 flex flex-col gap-1 ${color}`}>
      <span className="text-2xl font-bold">{count}</span>
      <span className="text-xs font-medium uppercase tracking-wider opacity-70">{label}</span>
    </div>
  );
}

export function AnalyticsPage({ book, chunks }: Props) {
  if (chunks.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-slate-400 text-sm">
        No chunks found for this book.
      </div>
    );
  }

  const approved = chunks.filter((c) => c.status === "approved").length;
  const inReview = chunks.filter((c) => c.status === "in_review").length;
  const raw = chunks.filter((c) => c.status === "raw").length;
  const failed = chunks.filter((c) =>
    c.editor_notes?.some((n) => n.startsWith("translation_failed"))
  ).length;
  const translated = chunks.filter((c) => c.translated_text).length;
  const progressPct = Math.round((translated / chunks.length) * 100);
  const approvalPct = Math.round((approved / chunks.length) * 100);

  const sourceCounts = chunks.map((c) => wordCount(c.source_text));
  const totalSourceWords = sourceCounts.reduce((a, b) => a + b, 0);
  const avgWords = Math.round(totalSourceWords / chunks.length);
  const maxWords = Math.max(...sourceCounts);
  const minWords = Math.min(...sourceCounts);
  const longestChunk = chunks[sourceCounts.indexOf(maxWords)];
  const shortestChunk = chunks[sourceCounts.indexOf(minWords)];

  const translatedSourceWords = chunks
    .filter((c) => c.translated_text)
    .reduce((sum, c) => sum + wordCount(c.source_text), 0);

  const translatedTargetWords = chunks
    .filter((c) => c.translated_text)
    .reduce((sum, c) => sum + wordCount(c.translated_text!), 0);

  const compressionRatio =
    translatedSourceWords > 0
      ? ((translatedTargetWords / translatedSourceWords) * 100).toFixed(1)
      : null;

  const barMax = Math.max(...sourceCounts, 1);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold tracking-tight">{book.title}</h2>
        <p className="text-sm text-slate-400">
          {book.author ?? "Unknown author"} · Translation analytics
        </p>
      </div>

      {/* Progress */}
      <div className="rounded-lg border border-slate-200 bg-white p-5 space-y-3">
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">Overall progress</h3>
        <div className="flex items-center gap-3">
          <div className="flex-1 h-3 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full transition-all duration-700"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <span className="text-sm font-semibold text-slate-700 shrink-0 w-12 text-right">
            {progressPct}%
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex-1 h-5 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all duration-700"
              style={{ width: `${approvalPct}%` }}
            />
          </div>
          <span className="text-sm font-semibold text-slate-700 shrink-0 w-12 text-right">
            {approvalPct}% <span className="text-xs font-normal text-emerald-600">approved</span>
          </span>
        </div>
        <p className="text-xs text-slate-400">
          {translated} of {chunks.length} chunks translated · {approved} approved
        </p>
      </div>

      {/* Status cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatusBadge label="Approved" count={approved} color="border-emerald-200 bg-emerald-50 text-emerald-800" />
        <StatusBadge label="In review" count={inReview} color="border-indigo-200 bg-indigo-50 text-indigo-800" />
        <StatusBadge label="Untranslated" count={raw} color="border-amber-200 bg-amber-50 text-amber-800" />
        <StatusBadge label="Failed" count={failed} color={failed > 0 ? "border-red-200 bg-red-50 text-red-800" : "border-slate-200 bg-slate-50 text-slate-400"} />
      </div>

      {/* Word stats */}
      <div className="rounded-lg border border-slate-200 bg-white p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">Word statistics</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <div>
            <p className="text-2xl font-bold text-slate-800">{totalSourceWords.toLocaleString()}</p>
            <p className="text-xs text-slate-500 mt-0.5">Total source words</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-800">{avgWords.toLocaleString()}</p>
            <p className="text-xs text-slate-500 mt-0.5">Avg words / chunk</p>
          </div>
          {compressionRatio && (
            <div>
              <p className="text-2xl font-bold text-slate-800">{compressionRatio}%</p>
              <p className="text-xs text-slate-500 mt-0.5">
                TR / EN ratio{" "}
                <span className={parseFloat(compressionRatio) > 100 ? "text-amber-500" : "text-emerald-600"}>
                  ({parseFloat(compressionRatio) > 100 ? "expanded" : "compressed"})
                </span>
              </p>
            </div>
          )}
        </div>
        <div className="flex gap-6 pt-1 border-t border-slate-100">
          <div className="text-sm">
            <span className="text-slate-500">Longest: </span>
            <span className="font-medium text-slate-800">{maxWords.toLocaleString()} words</span>
            <span className="ml-1 text-xs text-slate-400">(#{longestChunk.sequence_number})</span>
          </div>
          <div className="text-sm">
            <span className="text-slate-500">Shortest: </span>
            <span className="font-medium text-slate-800">{minWords.toLocaleString()} words</span>
            <span className="ml-1 text-xs text-slate-400">(#{shortestChunk.sequence_number})</span>
          </div>
        </div>
      </div>

      {/* Word count bar chart */}
      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wider mb-4">
          Word count per chunk
        </h3>
        <div className="flex items-end gap-px h-48 overflow-x-auto pb-1">
          {chunks.map((c, i) => {
            const pct = (sourceCounts[i] / barMax) * 100;
            const color =
              c.status === "approved"
                ? "bg-emerald-400"
                : c.status === "in_review"
                ? "bg-indigo-400"
                : "bg-amber-300";
            return (
              <div
                key={c.id}
                className="flex flex-col items-center group relative"
                style={{ minWidth: chunks.length > 60 ? "4px" : "8px", flex: "1 0 auto" }}
              >
                <div
                  className={`w-full rounded-t ${color} hover:opacity-80 transition-opacity cursor-default`}
                  style={{ height: `${pct}%`, minHeight: "2px" }}
                  title={`#${c.sequence_number}: ${sourceCounts[i]} words (${c.status})`}
                />
                {/* Tooltip */}
                <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 hidden group-hover:block z-10 pointer-events-none">
                  <div className="bg-slate-800 text-white text-xs rounded px-2 py-1 whitespace-nowrap shadow">
                    #{c.sequence_number} · {sourceCounts[i]}w · {c.status}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex gap-4 mt-3 flex-wrap">
          {[
            { color: "bg-emerald-400", label: "Approved" },
            { color: "bg-indigo-400", label: "In review" },
            { color: "bg-amber-300", label: "Untranslated" },
          ].map(({ color, label }) => (
            <div key={label} className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className={`inline-block w-2.5 h-2.5 rounded-sm ${color}`} />
              {label}
            </div>
          ))}
        </div>
      </div>

      {/* Top 5 longest chunks */}
      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wider mb-3">
          5 longest chunks
        </h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-slate-400 uppercase tracking-wider border-b border-slate-100">
              <th className="text-left pb-2 font-medium">Chunk</th>
              <th className="text-right pb-2 font-medium">Words</th>
              <th className="text-right pb-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {[...chunks]
              .sort((a, b) => wordCount(b.source_text) - wordCount(a.source_text))
              .slice(0, 10)
              .map((c) => (
                <tr key={c.id} className="hover:bg-slate-50">
                  <td className="py-2 font-mono text-slate-600">#{c.sequence_number}</td>
                  <td className="py-2 text-right font-medium">{wordCount(c.source_text).toLocaleString()}</td>
                  <td className="py-2 text-right">
                    <span className={`text-xs rounded-full px-2 py-0.5 ${
                      c.status === "approved"
                        ? "bg-emerald-100 text-emerald-700"
                        : c.status === "in_review"
                        ? "bg-indigo-100 text-indigo-700"
                        : "bg-amber-100 text-amber-700"
                    }`}>
                      {c.status}
                    </span>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
