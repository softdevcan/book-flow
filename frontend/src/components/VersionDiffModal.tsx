import { useEffect, useRef } from "react";
import { diffWordsWithSpace } from "diff";
import type { TranslationVersion } from "../types";

interface Props {
  activeVersion: TranslationVersion;
  otherVersion: TranslationVersion;
  onClose: () => void;
  onUse: (versionId: number) => void;
}

function fmtTime(iso: string) {
  const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
  return d.toLocaleString();
}

function versionLabel(v: TranslationVersion) {
  if (v.pipeline === "two_stage") {
    return `Two-stage · ${v.stage1_model ?? "?"} → ${v.stage2_model ?? "?"}`;
  }
  return `${v.pipeline ?? "single"} · ${v.stage1_model ?? "?"}`;
}

export function VersionDiffModal({ activeVersion, otherVersion, onClose, onUse }: Props) {
  const overlayRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // Close on click outside
  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onClose();
  }

  const diff = diffWordsWithSpace(activeVersion.translated_text, otherVersion.translated_text);

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Version comparison"
    >
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200 dark:border-slate-700">
          <h2 className="font-semibold text-slate-800 dark:text-slate-100">Version comparison</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {/* Metadata strip */}
        <div className="grid grid-cols-2 gap-4 px-5 py-3 text-xs bg-slate-50 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
          <div>
            <p className="font-medium text-indigo-600 dark:text-indigo-400 mb-0.5">Active</p>
            <p className="text-slate-500 dark:text-slate-400">{versionLabel(activeVersion)}</p>
            <p className="text-slate-400 dark:text-slate-500">{fmtTime(activeVersion.created_at)}</p>
          </div>
          <div>
            <p className="font-medium text-amber-600 dark:text-amber-400 mb-0.5">Compare</p>
            <p className="text-slate-500 dark:text-slate-400">{versionLabel(otherVersion)}</p>
            <p className="text-slate-400 dark:text-slate-500">{fmtTime(otherVersion.created_at)}</p>
          </div>
        </div>

        {/* Diff body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">
            <span className="inline-block bg-red-100 dark:bg-red-900/40 line-through px-1 rounded mr-1">removed</span>
            from active ·
            <span className="inline-block bg-emerald-100 dark:bg-emerald-900/40 px-1 rounded ml-1">added</span>
            in compare
          </p>
          <p className="text-sm font-serif leading-relaxed whitespace-pre-wrap text-slate-800 dark:text-slate-200">
            {diff.map((part, i) => {
              if (part.removed) {
                return (
                  <del key={i} className="bg-red-100 dark:bg-red-900/40 line-through text-red-700 dark:text-red-300">
                    {part.value}
                  </del>
                );
              }
              if (part.added) {
                return (
                  <ins key={i} className="bg-emerald-100 dark:bg-emerald-900/40 no-underline text-emerald-800 dark:text-emerald-300">
                    {part.value}
                  </ins>
                );
              }
              return <span key={i}>{part.value}</span>;
            })}
          </p>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-5 py-3 border-t border-slate-200 dark:border-slate-700">
          <button
            onClick={onClose}
            className="text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
          >
            Cancel
          </button>
          <button
            onClick={() => { onUse(otherVersion.id); onClose(); }}
            className="text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded px-4 py-1.5"
          >
            Use this version
          </button>
        </div>
      </div>
    </div>
  );
}
