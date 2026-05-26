import { useEffect, useCallback } from "react";

interface Options {
  enabled: boolean;
  chunkIds: number[];
  focusedChunkId: number | null;
  onFocus: (id: number) => void;
  onTranslate: (id: number) => void;
  onApprove: (id: number) => void;
  onEdit: (id: number) => void;
  onFocusSearch: () => void;
  onHelp: () => void;
}

function isInputFocused(): boolean {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName.toLowerCase();
  return (
    tag === "input" ||
    tag === "textarea" ||
    (el as HTMLElement).isContentEditable
  );
}

export function useChunkKeybindings({
  enabled,
  chunkIds,
  focusedChunkId,
  onFocus,
  onTranslate,
  onApprove,
  onEdit,
  onFocusSearch,
  onHelp,
}: Options) {
  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (!enabled) return;
      if (isInputFocused()) return;
      // Don't fire on modifier combos
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      const currentIdx = focusedChunkId !== null
        ? chunkIds.indexOf(focusedChunkId)
        : -1;

      switch (e.key) {
        case "j": {
          e.preventDefault();
          const next = currentIdx < chunkIds.length - 1 ? currentIdx + 1 : 0;
          onFocus(chunkIds[next]);
          scrollToChunk(chunkIds[next]);
          break;
        }
        case "k": {
          e.preventDefault();
          const prev = currentIdx > 0 ? currentIdx - 1 : chunkIds.length - 1;
          onFocus(chunkIds[prev]);
          scrollToChunk(chunkIds[prev]);
          break;
        }
        case "t": {
          e.preventDefault();
          if (focusedChunkId !== null) onTranslate(focusedChunkId);
          break;
        }
        case "a": {
          e.preventDefault();
          if (focusedChunkId !== null) onApprove(focusedChunkId);
          break;
        }
        case "e": {
          e.preventDefault();
          if (focusedChunkId !== null) onEdit(focusedChunkId);
          break;
        }
        case "/": {
          e.preventDefault();
          onFocusSearch();
          break;
        }
        case "?": {
          e.preventDefault();
          onHelp();
          break;
        }
      }
    },
    [enabled, chunkIds, focusedChunkId, onFocus, onTranslate, onApprove, onEdit, onFocusSearch, onHelp],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [handleKey]);
}

function scrollToChunk(chunkId: number) {
  const el = document.querySelector(`[data-chunk-id="${chunkId}"]`);
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}
