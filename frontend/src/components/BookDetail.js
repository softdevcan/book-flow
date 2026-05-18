import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { ModelPicker } from "./ModelPicker";
import { GlossaryPanel } from "./GlossaryPanel";
import { ChunkCard } from "./ChunkCard";
export function BookDetail({ bookId, onBack }) {
    const [book, setBook] = useState(null);
    const [chunks, setChunks] = useState([]);
    const [selectedModel, setSelectedModel] = useState(null);
    const [error, setError] = useState(null);
    const pollRef = useRef(null);
    async function loadAll() {
        try {
            const [b, c] = await Promise.all([api.getBook(bookId), api.listChunks(bookId)]);
            setBook(b);
            setChunks(c);
            setError(null);
        }
        catch (e) {
            setError(String(e));
        }
    }
    useEffect(() => {
        loadAll();
    }, [bookId]);
    useEffect(() => {
        const anyRaw = chunks.some((c) => c.status === "raw" && c.translated_text === null);
        if (!anyRaw) {
            if (pollRef.current) {
                window.clearInterval(pollRef.current);
                pollRef.current = null;
            }
            return;
        }
        if (pollRef.current)
            return;
        pollRef.current = window.setInterval(loadAll, 3000);
        return () => {
            if (pollRef.current) {
                window.clearInterval(pollRef.current);
                pollRef.current = null;
            }
        };
    }, [chunks]);
    async function translateAll() {
        await api.translateBook(bookId, { model: selectedModel ?? undefined });
        loadAll();
    }
    async function translateOne(id) {
        await api.translateChunk(id, { model: selectedModel ?? undefined });
        loadAll();
    }
    async function updateChunk(id, patch) {
        const updated = await api.updateChunk(id, patch);
        setChunks((prev) => prev.map((c) => (c.id === id ? updated : c)));
    }
    if (!book) {
        return _jsx("p", { className: "text-sm text-slate-500", children: "Loading\u2026" });
    }
    const counts = chunks.reduce((acc, c) => {
        acc[c.status]++;
        return acc;
    }, { raw: 0, in_review: 0, approved: 0 });
    return (_jsxs("div", { className: "space-y-6", children: [_jsx("button", { onClick: onBack, className: "text-sm text-indigo-600 hover:underline", children: "\u2190 Back to library" }), _jsxs("header", { className: "flex items-start justify-between gap-4 flex-wrap", children: [_jsxs("div", { children: [_jsx("h1", { className: "text-2xl font-bold tracking-tight", children: book.title }), _jsxs("p", { className: "text-sm text-slate-500", children: [book.author ?? "Unknown author", " \u00B7 ", book.total_chunks, " chunks \u00B7", " ", _jsxs("span", { className: "text-amber-600", children: [counts.raw, " raw"] }), " \u00B7", " ", _jsxs("span", { className: "text-indigo-600", children: [counts.in_review, " in review"] }), " \u00B7", " ", _jsxs("span", { className: "text-emerald-600", children: [counts.approved, " approved"] })] })] }), _jsxs("div", { className: "flex items-center gap-3", children: [_jsx(ModelPicker, { selected: selectedModel, onChange: setSelectedModel }), _jsx("button", { onClick: translateAll, className: "bg-indigo-600 hover:bg-indigo-700 text-white text-sm rounded px-3 py-1.5", children: "Translate all pending" })] })] }), error && (_jsx("div", { className: "rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700", children: error })), _jsxs("div", { className: "grid lg:grid-cols-[1fr_320px] gap-6", children: [_jsx("section", { className: "space-y-4", children: chunks.map((c) => (_jsx(ChunkCard, { chunk: c, onTranslate: () => translateOne(c.id), onUpdate: (patch) => updateChunk(c.id, patch) }, c.id))) }), _jsxs("aside", { className: "space-y-4", children: [_jsx(GlossaryPanel, { bookId: bookId }), book.style_guide && (_jsxs("div", { className: "rounded-lg border border-slate-200 bg-white p-4", children: [_jsx("h3", { className: "font-semibold mb-2", children: "Style guide" }), _jsx("p", { className: "text-sm whitespace-pre-wrap text-slate-700", children: book.style_guide })] }))] })] })] }));
}
