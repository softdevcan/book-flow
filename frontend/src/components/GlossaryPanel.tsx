import { useEffect, useState } from "react";
import { api } from "../api";
import type { GlossaryTerm } from "../types";

interface Props {
  bookId: number;
}

export function GlossaryPanel({ bookId }: Props) {
  const [terms, setTerms] = useState<GlossaryTerm[]>([]);
  const [src, setSrc] = useState("");
  const [tgt, setTgt] = useState("");

  async function load() {
    setTerms(await api.listGlossary(bookId));
  }

  useEffect(() => {
    load();
  }, [bookId]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!src.trim() || !tgt.trim()) return;
    await api.addGlossaryTerm(bookId, src.trim(), tgt.trim());
    setSrc("");
    setTgt("");
    load();
  }

  async function remove(id: number) {
    await api.deleteGlossaryTerm(id);
    load();
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="font-semibold mb-2">Glossary</h3>
      <p className="text-xs text-slate-500 mb-3">
        Strict translations applied to every chunk.
      </p>
      <form onSubmit={add} className="flex gap-2 mb-3">
        <input
          value={src}
          onChange={(e) => setSrc(e.target.value)}
          placeholder="source"
          className="flex-1 text-sm border border-slate-300 rounded px-2 py-1"
        />
        <input
          value={tgt}
          onChange={(e) => setTgt(e.target.value)}
          placeholder="target"
          className="flex-1 text-sm border border-slate-300 rounded px-2 py-1"
        />
        <button className="text-sm bg-slate-800 text-white rounded px-3">
          Add
        </button>
      </form>
      {terms.length === 0 ? (
        <p className="text-xs text-slate-400">No terms yet.</p>
      ) : (
        <ul className="space-y-1 max-h-48 overflow-y-auto">
          {terms.map((t) => (
            <li
              key={t.id}
              className="flex justify-between text-sm border border-slate-100 rounded px-2 py-1"
            >
              <span>
                <strong>{t.source_term}</strong> →{" "}
                <span className="text-indigo-700">{t.target_term}</span>
              </span>
              <button
                onClick={() => remove(t.id)}
                className="text-xs text-red-500 hover:underline"
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
