import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { api } from "../api";
import { UploadForm } from "./UploadForm";
export function BookList({ onOpen }) {
    const [books, setBooks] = useState([]);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
    async function reload() {
        setLoading(true);
        try {
            setBooks(await api.listBooks());
            setError(null);
        }
        catch (e) {
            setError(String(e));
        }
        finally {
            setLoading(false);
        }
    }
    useEffect(() => {
        reload();
    }, []);
    return (_jsxs("div", { className: "grid lg:grid-cols-[1fr_400px] gap-8", children: [_jsxs("section", { children: [_jsx("h1", { className: "text-2xl font-bold tracking-tight mb-1", children: "Library" }), _jsx("p", { className: "text-sm text-slate-500 mb-5", children: "Upload an EPUB, PDF, DOCX or TXT file. BookFlow will parse it, split it into translation-friendly chunks, and let you translate them chunk-by-chunk into Turkish." }), error && (_jsx("div", { className: "mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700", children: error })), loading && books.length === 0 ? (_jsx("p", { className: "text-sm text-slate-500", children: "Loading\u2026" })) : books.length === 0 ? (_jsx("p", { className: "text-sm text-slate-500", children: "No books yet. Upload one on the right to get started." })) : (_jsx("ul", { className: "divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white", children: books.map((b) => (_jsx("li", { children: _jsxs("button", { onClick: () => onOpen(b.id), className: "w-full text-left px-4 py-3 hover:bg-slate-50 flex justify-between items-center", children: [_jsxs("div", { children: [_jsx("div", { className: "font-medium", children: b.title }), _jsxs("div", { className: "text-xs text-slate-500", children: [b.author ?? "Unknown author", " \u00B7 ", b.total_chunks, " chunks"] })] }), _jsx("span", { className: "text-slate-400", children: "\u2192" })] }) }, b.id))) }))] }), _jsx("aside", { children: _jsx(UploadForm, { onUploaded: reload }) })] }));
}
