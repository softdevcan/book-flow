import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { api } from "../api";
export function GlossaryPanel({ bookId }) {
    const [terms, setTerms] = useState([]);
    const [src, setSrc] = useState("");
    const [tgt, setTgt] = useState("");
    async function load() {
        setTerms(await api.listGlossary(bookId));
    }
    useEffect(() => {
        load();
    }, [bookId]);
    async function add(e) {
        e.preventDefault();
        if (!src.trim() || !tgt.trim())
            return;
        await api.addGlossaryTerm(bookId, src.trim(), tgt.trim());
        setSrc("");
        setTgt("");
        load();
    }
    async function remove(id) {
        await api.deleteGlossaryTerm(id);
        load();
    }
    return (_jsxs("div", { className: "rounded-lg border border-slate-200 bg-white p-4", children: [_jsx("h3", { className: "font-semibold mb-2", children: "Glossary" }), _jsx("p", { className: "text-xs text-slate-500 mb-3", children: "Strict translations applied to every chunk." }), _jsxs("form", { onSubmit: add, className: "flex gap-2 mb-3", children: [_jsx("input", { value: src, onChange: (e) => setSrc(e.target.value), placeholder: "source", className: "flex-1 text-sm border border-slate-300 rounded px-2 py-1" }), _jsx("input", { value: tgt, onChange: (e) => setTgt(e.target.value), placeholder: "target", className: "flex-1 text-sm border border-slate-300 rounded px-2 py-1" }), _jsx("button", { className: "text-sm bg-slate-800 text-white rounded px-3", children: "Add" })] }), terms.length === 0 ? (_jsx("p", { className: "text-xs text-slate-400", children: "No terms yet." })) : (_jsx("ul", { className: "space-y-1 max-h-48 overflow-y-auto", children: terms.map((t) => (_jsxs("li", { className: "flex justify-between text-sm border border-slate-100 rounded px-2 py-1", children: [_jsxs("span", { children: [_jsx("strong", { children: t.source_term }), " \u2192", " ", _jsx("span", { className: "text-indigo-700", children: t.target_term })] }), _jsx("button", { onClick: () => remove(t.id), className: "text-xs text-red-500 hover:underline", children: "remove" })] }, t.id))) }))] }));
}
