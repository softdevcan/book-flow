import { useState } from "react";
import { BookList } from "./components/BookList";
import { BookDetail } from "./components/BookDetail";
import { ThemeToggle } from "./components/ThemeToggle";

export function App() {
  const [activeBookId, setActiveBookId] = useState<number | null>(null);

  return (
    <div className="min-h-screen flex flex-col bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div className="w-full px-6 py-4 flex items-center justify-between">
          <button
            onClick={() => setActiveBookId(null)}
            className="flex items-center gap-2 text-lg font-semibold tracking-tight hover:opacity-80"
          >
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-indigo-500" />
            BookFlow
          </button>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500 dark:text-slate-400">
              AI-assisted literary translation
            </span>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="flex-1 w-full px-6 py-8">
        {activeBookId === null ? (
          <BookList onOpen={setActiveBookId} />
        ) : (
          <BookDetail bookId={activeBookId} onBack={() => setActiveBookId(null)} />
        )}
      </main>

      <footer className="border-t border-slate-200 dark:border-slate-800 text-center text-xs text-slate-400 dark:text-slate-500 py-3">
        BookFlow · local Ollama / OpenRouter provider
      </footer>
    </div>
  );
}
