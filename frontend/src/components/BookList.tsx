import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../api";
import type { Book } from "../types";
import { UploadForm } from "./UploadForm";

interface Props {
  onOpen: (id: number) => void;
}

export function BookList({ onOpen }: Props) {
  const [books, setBooks] = useState<Book[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);

  async function handleDelete(e: React.MouseEvent, id: number) {
    e.stopPropagation();
    if (!confirm("Delete this book and all its chunks?")) return;
    setDeleting(id);
    try {
      await api.deleteBook(id);
      await reload();
      toast.success("Book deleted");
    } catch (err) {
      setError(String(err));
      toast.error(`Delete failed: ${err}`);
    } finally {
      setDeleting(null);
    }
  }

  async function reload() {
    setLoading(true);
    try {
      setBooks(await api.listBooks());
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  return (
    <div className="grid lg:grid-cols-[1fr_400px] gap-8">
      <section>
        <h1 className="text-2xl font-bold tracking-tight mb-1 text-slate-900 dark:text-slate-100">Library</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-5">
          Upload an EPUB, PDF, DOCX or TXT file. BookFlow will parse it, split
          it into translation-friendly chunks, and let you translate them
          chunk-by-chunk into your target language.
        </p>

        {error && (
          <div className="mb-4 rounded border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-700 dark:text-red-400">
            {error}
          </div>
        )}

        {loading && books.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">Loading…</p>
        ) : books.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            No books yet. Upload one on the right to get started.
          </p>
        ) : (
          <ul className="divide-y divide-slate-200 dark:divide-slate-700 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
            {books.map((b) => (
              <li key={b.id}>
                <button
                  onClick={() => onOpen(b.id)}
                  className="w-full text-left px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800 flex justify-between items-center transition-colors"
                >
                  <div>
                    <div className="font-medium text-slate-900 dark:text-slate-100">{b.title}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {b.author ?? "Unknown author"} · {b.total_chunks} chunks ·{" "}
                      {b.source_language.toUpperCase()} → {b.target_language.toUpperCase()}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => handleDelete(e, b.id)}
                      disabled={deleting === b.id}
                      className="text-xs text-red-400 hover:text-red-600 dark:text-red-500 dark:hover:text-red-400 px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-40"
                    >
                      {deleting === b.id ? "…" : "Delete"}
                    </button>
                    <span className="text-slate-400 dark:text-slate-500">→</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <aside>
        <UploadForm onUploaded={reload} />
      </aside>
    </div>
  );
}
