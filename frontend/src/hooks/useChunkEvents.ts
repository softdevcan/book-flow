import { useEffect, useRef } from "react";

export interface ChunkEvent {
  type: "chunk_updated" | "chunk_failed" | "batch_progress";
  chunk_id?: number;
  status?: string;
  translated?: boolean;
  failed?: boolean;
  reason?: string;
  phase?: "stage1" | "stage2";
  done?: number;
  total?: number;
}

/**
 * Opens an SSE stream for a book and calls `onChange` on each event.
 * Closes and cleans up when bookId changes or component unmounts.
 */
export function useChunkEvents(
  bookId: number,
  onChange: (e: ChunkEvent) => void,
  enabled = true,
) {
  // Stable ref so onChange identity changes don't restart the stream.
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!enabled) return;

    const es = new EventSource(`/api/books/${bookId}/events`);

    const EVENT_TYPES: ChunkEvent["type"][] = [
      "chunk_updated",
      "chunk_failed",
      "batch_progress",
    ];

    EVENT_TYPES.forEach((t) => {
      es.addEventListener(t, (ev) => {
        try {
          const data = JSON.parse((ev as MessageEvent).data);
          onChangeRef.current({ type: t, ...data });
        } catch {}
      });
    });

    es.onerror = () => {
      // Browser will reconnect automatically; nothing extra needed.
    };

    return () => {
      es.close();
    };
  }, [bookId, enabled]);
}
