import { useState } from "react";
import { BookList } from "./components/BookList";
import { BookDetail } from "./components/BookDetail";

export function App() {
  const [activeBookId, setActiveBookId] = useState<number | null>(null);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-screen-2xl mx-auto px-6 py-4 flex items-center justify-between">
          <button
            onClick={() => setActiveBookId(null)}
            className="flex items-center gap-2 text-lg font-semibold tracking-tight hover:opacity-80"
          >
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-indigo-500" />
            BookFlow
          </button>
          <span className="text-xs text-slate-500">
            AI-assisted literary translation
          </span>
        </div>
      </header>

      <main className="flex-1 max-w-screen-2xl w-full mx-auto px-6 py-8">
        {activeBookId === null ? (
          <BookList onOpen={setActiveBookId} />
        ) : (
          <BookDetail bookId={activeBookId} onBack={() => setActiveBookId(null)} />
        )}
      </main>

      <footer className="border-t border-slate-200 text-center text-xs text-slate-400 py-3">
        BookFlow · local Ollama / OpenRouter provider
      </footer>
    </div>
  );
}
