import { useRef, type KeyboardEvent } from "react";

export type StatusFilter = "all" | "raw" | "in_review" | "approved" | "failed";

interface Props {
  statusFilter: StatusFilter;
  searchText: string;
  onStatusChange: (s: StatusFilter) => void;
  onSearchChange: (text: string) => void;
  counts: Record<StatusFilter, number>;
  searchInputRef?: React.RefObject<HTMLInputElement | null>;
}

const STATUS_CHIPS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "raw", label: "Raw" },
  { key: "in_review", label: "In review" },
  { key: "approved", label: "Approved" },
  { key: "failed", label: "Failed" },
];

export function ChunkFilterBar({
  statusFilter,
  searchText,
  onStatusChange,
  onSearchChange,
  counts,
  searchInputRef,
}: Props) {
  const internalRef = useRef<HTMLInputElement>(null);
  const inputRef = searchInputRef ?? internalRef;

  function handleSearchKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") {
      onSearchChange("");
      (inputRef as React.RefObject<HTMLInputElement>).current?.blur();
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Status chips */}
      <div className="flex items-center gap-1 flex-wrap">
        {STATUS_CHIPS.map(({ key, label }) => {
          const active = statusFilter === key;
          return (
            <button
              key={key}
              onClick={() => onStatusChange(key)}
              className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                active
                  ? "bg-indigo-600 border-indigo-600 text-white"
                  : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-indigo-300 dark:hover:border-indigo-600"
              }`}
            >
              {label}
              {key !== "all" && counts[key] > 0 && (
                <span className={`ml-1 ${active ? "opacity-80" : "text-slate-400 dark:text-slate-500"}`}>
                  {counts[key]}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Text search */}
      <div className="relative flex-1 min-w-[180px]">
        <svg
          className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 w-3.5 h-3.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
        </svg>
        <input
          ref={inputRef as React.RefObject<HTMLInputElement>}
          type="text"
          value={searchText}
          onChange={(e) => onSearchChange(e.target.value)}
          onKeyDown={handleSearchKey}
          placeholder="Search chunks… (/)"
          className="w-full pl-8 pr-3 py-1.5 text-xs rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-400"
        />
        {searchText && (
          <button
            onClick={() => onSearchChange("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
}
