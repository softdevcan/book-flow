import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { api } from "../api";
export function ModelPicker({ selected, onChange }) {
    const [models, setModels] = useState([]);
    const [defaultModel, setDefaultModel] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
    async function load() {
        setLoading(true);
        try {
            const res = await api.listModels();
            setModels(res.models);
            setDefaultModel(res.active_default);
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
        load();
    }, []);
    return (_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("label", { className: "text-xs font-medium text-slate-600", children: "Model:" }), _jsxs("select", { value: selected ?? "", onChange: (e) => onChange(e.target.value || null), className: "text-sm rounded border border-slate-300 bg-white px-2 py-1", children: [_jsx("option", { value: "", children: defaultModel ? `Default (${defaultModel})` : "Default" }), models.map((m) => (_jsx("option", { value: m, children: m }, m)))] }), _jsx("button", { type: "button", onClick: load, className: "text-xs text-indigo-600 hover:underline", disabled: loading, children: loading ? "…" : "refresh" }), error && _jsx("span", { className: "text-xs text-red-600", children: error })] }));
}
