import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import type { GlossaryTerm } from "../types";

interface Props {
  bookId: number;
}

export function GlossaryPanel({ bookId }: Props) {
  const [terms, setTerms] = useState<GlossaryTerm[]>([]);
  const [src, setSrc] = useState("");
  const [tgt, setTgt] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false;
      setError(null);
      if (!silent) setIsLoading(true);
      try {
        setTerms(await api.listGlossary(bookId));
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to load glossary.";
        setError(message);
        setTerms([]);
      } finally {
        if (!silent) setIsLoading(false);
      }
    },
    [bookId],
  );

  useEffect(() => {
    void load();
  }, [load]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!src.trim() || !tgt.trim()) return;
    setError(null);
    try {
      await api.addGlossaryTerm(bookId, src.trim(), tgt.trim());
      setSrc("");
      setTgt("");
      await load({ silent: true });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to add glossary term.";
      setError(message);
    }
  }

  async function handleRemove(id: number) {
    setError(null);
    try {
      await api.deleteGlossaryTerm(id);
      await load({ silent: true });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to remove glossary term.";
      setError(message);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4">
      <h3 className="font-semibold mb-2 text-slate-800 dark:text-slate-100">Glossary</h3>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
        Strict translations applied to every chunk.
      </p>
      {error ? (
        <p className="text-xs text-red-600 dark:text-red-400 mb-3" role="alert">
          {error}
        </p>
      ) : null}
      <form onSubmit={handleSubmit} className="flex gap-2 mb-3">
        <input
          value={src}
          onChange={(e) => setSrc(e.target.value)}
          placeholder="source"
          className="flex-1 text-sm border border-slate-300 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-400"
          disabled={isLoading}
          aria-label="Source term"
        />
        <input
          value={tgt}
          onChange={(e) => setTgt(e.target.value)}
          placeholder="target"
          className="flex-1 text-sm border border-slate-300 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-400"
          disabled={isLoading}
          aria-label="Target term"
        />
        <button
          type="submit"
          className="text-sm bg-slate-800 dark:bg-slate-700 text-white rounded px-3 py-1 disabled:opacity-50 hover:bg-slate-700 dark:hover:bg-slate-600"
          disabled={isLoading}
        >
          Add
        </button>
      </form>
      {isLoading ? (
        <p className="text-xs text-slate-400 dark:text-slate-500">Loading glossary…</p>
      ) : terms.length === 0 ? (
        <p className="text-xs text-slate-400 dark:text-slate-500">No terms yet.</p>
      ) : (
        <ul className="space-y-1 max-h-48 overflow-y-auto">
          {terms.map((t) => (
            <li
              key={t.id}
              className="flex justify-between text-sm border border-slate-100 dark:border-slate-700 rounded px-2 py-1"
            >
              <span className="text-slate-800 dark:text-slate-200">
                <strong>{t.source_term}</strong> →{" "}
                <span className="text-indigo-700 dark:text-indigo-400">{t.target_term}</span>
              </span>
              <button
                type="button"
                onClick={() => void handleRemove(t.id)}
                className="text-xs text-red-500 dark:text-red-400 hover:underline"
              >
                remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
