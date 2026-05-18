import { useEffect, useState } from "react";
import { api } from "../api";

interface Props {
  selected: string | null;
  onChange: (model: string | null) => void;
}

export function ModelPicker({ selected, onChange }: Props) {
  const [models, setModels] = useState<string[]>([]);
  const [defaultModel, setDefaultModel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await api.listModels();
      setModels(res.models);
      setDefaultModel(res.active_default);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="flex items-center gap-2">
      <label className="text-xs font-medium text-slate-600">Model:</label>
      <select
        value={selected ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="text-sm rounded border border-slate-300 bg-white px-2 py-1"
      >
        <option value="">
          {defaultModel ? `Default (${defaultModel})` : "Default"}
        </option>
        {models.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={load}
        className="text-xs text-indigo-600 hover:underline"
        disabled={loading}
      >
        {loading ? "…" : "refresh"}
      </button>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}
