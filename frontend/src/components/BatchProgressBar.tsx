import { useEffect, useRef, useState } from "react";
import type { ChunkEvent } from "../hooks/useChunkEvents";

interface Props {
  totalChunks: number;
  translatedChunks: number;
  lastBatchEvent: ChunkEvent | null;
}

/** Sticky top progress bar shown while a batch translation is running.
 *  Disappears 30 s after the last batch_progress event arrives. */
export function BatchProgressBar({ totalChunks, translatedChunks, lastBatchEvent }: Props) {
  const [visible, setVisible] = useState(false);
  const hideTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!lastBatchEvent) return;
    setVisible(true);
    if (hideTimerRef.current) window.clearTimeout(hideTimerRef.current);
    hideTimerRef.current = window.setTimeout(() => setVisible(false), 30_000);
    return () => {
      if (hideTimerRef.current) window.clearTimeout(hideTimerRef.current);
    };
  }, [lastBatchEvent]);

  if (!visible || totalChunks === 0) return null;

  const pct = Math.round((translatedChunks / totalChunks) * 100);
  const phase = lastBatchEvent?.phase;
  const done = lastBatchEvent?.done ?? 0;
  const total = lastBatchEvent?.total ?? totalChunks;

  return (
    <div className="sticky top-0 z-30 bg-white dark:bg-slate-900 border-b border-indigo-100 dark:border-indigo-900 shadow-sm px-4 py-2 flex items-center gap-3">
      <div className="flex-1 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-indigo-500 rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-slate-600 dark:text-slate-300 shrink-0 tabular-nums">
        {phase ? (
          <>
            <span className="font-medium text-indigo-600 dark:text-indigo-400">
              {phase === "stage1" ? "Stage 1" : "Stage 2"}
            </span>
            {" · "}
            {done}/{total}
          </>
        ) : (
          <>{translatedChunks}/{totalChunks} translated</>
        )}
      </span>
      <span className="text-xs text-slate-400 dark:text-slate-500 tabular-nums">{pct}%</span>
    </div>
  );
}
