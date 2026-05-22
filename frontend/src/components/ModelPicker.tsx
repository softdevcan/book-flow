import { useEffect, useState } from "react";
import { api } from "../api";

interface Props {
  selected: string | null;
  onChange: (model: string | null) => void;
  label?: string;
  /** The model this stage falls back to when nothing is selected (e.g. the
   *  .env stage default). Shown in the "Default (...)" option and checked
   *  against the installed list. */
  defaultModel?: string | null;
}

export function ModelPicker({
  selected,
  onChange,
  label = "Model",
  defaultModel,
}: Props) {
  const [models, setModels] = useState<string[]>([]);
  const [activeDefault, setActiveDefault] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await api.listModels();
      setModels(res.models);
      setActiveDefault(res.active_default);
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

  // What this picker falls back to: an explicit per-stage default if given,
  // else the server's active (installed) default.
  const effectiveDefault = defaultModel ?? activeDefault;
  // Warn only once models are loaded and the fallback is genuinely missing.
  const defaultMissing =
    models.length > 0 &&
    effectiveDefault != null &&
    !models.includes(effectiveDefault);

  return (
    <div className="flex items-center gap-2">
      <label className="text-xs font-medium text-slate-600">{label}:</label>
      <select
        value={selected ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="text-sm rounded border border-slate-300 bg-white px-2 py-1"
      >
        <option value="">
          {effectiveDefault ? `Default (${effectiveDefault})` : "Default"}
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
      {defaultMissing && !selected && (
        <span
          className="text-xs text-amber-600"
          title={`"${effectiveDefault}" is configured but not installed in Ollama. Pick an installed model, or run: ollama pull ${effectiveDefault}`}
        >
          ⚠ default not installed
        </span>
      )}
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}
