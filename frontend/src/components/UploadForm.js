import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { api } from "../api";
export function UploadForm({ onUploaded }) {
    const [file, setFile] = useState(null);
    const [title, setTitle] = useState("");
    const [author, setAuthor] = useState("");
    const [styleGuide, setStyleGuide] = useState("");
    const [maxChars, setMaxChars] = useState(2000);
    const [busy, setBusy] = useState(false);
    const [msg, setMsg] = useState(null);
    async function submit(e) {
        e.preventDefault();
        if (!file) {
            setMsg({ kind: "err", text: "Please choose a file" });
            return;
        }
        const form = new FormData();
        form.append("file", file);
        if (title)
            form.append("title", title);
        if (author)
            form.append("author", author);
        if (styleGuide)
            form.append("style_guide", styleGuide);
        form.append("max_chars", String(maxChars));
        setBusy(true);
        setMsg(null);
        try {
            const book = await api.uploadBook(form);
            setMsg({
                kind: "ok",
                text: `Uploaded "${book.title}" — ${book.total_chunks} chunks ready.`,
            });
            setFile(null);
            setTitle("");
            setAuthor("");
            setStyleGuide("");
            onUploaded();
        }
        catch (e) {
            setMsg({ kind: "err", text: String(e) });
        }
        finally {
            setBusy(false);
        }
    }
    return (_jsxs("form", { onSubmit: submit, className: "rounded-lg border border-slate-200 bg-white p-5 space-y-3", children: [_jsx("h2", { className: "font-semibold", children: "Upload a book" }), _jsx("p", { className: "text-xs text-slate-500 -mt-2", children: "Accepted: .epub, .pdf, .docx, .txt, .md (max 50 MB)" }), _jsx("input", { type: "file", accept: ".epub,.pdf,.docx,.txt,.md", onChange: (e) => setFile(e.target.files?.[0] ?? null), className: "block w-full text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100" }), _jsx(Field, { label: "Title (optional)", children: _jsx("input", { value: title, onChange: (e) => setTitle(e.target.value), placeholder: "Auto-detected from file metadata", className: "input" }) }), _jsx(Field, { label: "Author (optional)", children: _jsx("input", { value: author, onChange: (e) => setAuthor(e.target.value), className: "input" }) }), _jsx(Field, { label: "Style guide (optional)", children: _jsx("textarea", { value: styleGuide, onChange: (e) => setStyleGuide(e.target.value), rows: 3, placeholder: "Genre: Cyberpunk Sci-Fi. Tone is gritty\u2026", className: "input" }) }), _jsx(Field, { label: `Chunk size: ~${maxChars} chars`, children: _jsx("input", { type: "range", min: 500, max: 4000, step: 100, value: maxChars, onChange: (e) => setMaxChars(parseInt(e.target.value)), className: "w-full" }) }), _jsx("button", { disabled: busy, className: "w-full bg-indigo-600 text-white rounded py-2 text-sm font-medium hover:bg-indigo-700 disabled:opacity-60", children: busy ? "Uploading…" : "Upload & chunk" }), msg && (_jsx("div", { className: `text-sm rounded px-3 py-2 ${msg.kind === "ok"
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-red-50 text-red-700 border border-red-200"}`, children: msg.text })), _jsx("style", { children: `
        .input {
          width: 100%;
          border: 1px solid rgb(226 232 240);
          border-radius: 6px;
          padding: 6px 10px;
          font-size: 14px;
          background: white;
        }
        .input:focus { outline: 2px solid rgb(99 102 241); outline-offset: -1px; }
      ` })] }));
}
function Field({ label, children }) {
    return (_jsxs("label", { className: "block", children: [_jsx("span", { className: "block text-xs font-medium text-slate-600 mb-1", children: label }), children] }));
}
