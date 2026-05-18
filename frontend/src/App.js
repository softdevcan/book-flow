import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { BookList } from "./components/BookList";
import { BookDetail } from "./components/BookDetail";
export function App() {
    const [activeBookId, setActiveBookId] = useState(null);
    return (_jsxs("div", { className: "min-h-screen flex flex-col", children: [_jsx("header", { className: "border-b border-slate-200 bg-white", children: _jsxs("div", { className: "max-w-6xl mx-auto px-6 py-4 flex items-center justify-between", children: [_jsxs("button", { onClick: () => setActiveBookId(null), className: "flex items-center gap-2 text-lg font-semibold tracking-tight hover:opacity-80", children: [_jsx("span", { className: "inline-block w-2.5 h-2.5 rounded-full bg-indigo-500" }), "BookFlow"] }), _jsx("span", { className: "text-xs text-slate-500", children: "AI-assisted literary translation \u00B7 EN \u2192 TR" })] }) }), _jsx("main", { className: "flex-1 max-w-6xl w-full mx-auto px-6 py-8", children: activeBookId === null ? (_jsx(BookList, { onOpen: setActiveBookId })) : (_jsx(BookDetail, { bookId: activeBookId, onBack: () => setActiveBookId(null) })) }), _jsx("footer", { className: "border-t border-slate-200 text-center text-xs text-slate-400 py-3", children: "BookFlow \u00B7 local Ollama / OpenRouter provider" })] }));
}
