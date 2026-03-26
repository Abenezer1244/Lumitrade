"use client";

import { RotateCcw } from "lucide-react";

interface TradeFiltersData {
  pair: string;
  outcome: string;
  dateFrom: string;
  dateTo: string;
}

interface TradeFiltersProps {
  filters: TradeFiltersData;
  onChange: (filters: TradeFiltersData) => void;
}

const PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY"];

const OUTCOMES = ["WIN", "LOSS", "BREAKEVEN"];

const selectClasses =
  "bg-input border border-border rounded-lg px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent transition-colors appearance-none cursor-pointer";

const inputClasses =
  "bg-input border border-border rounded-lg px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent transition-colors";

export default function TradeFilters({ filters, onChange }: TradeFiltersProps) {
  function update(key: keyof TradeFiltersData, value: string) {
    onChange({ ...filters, [key]: value });
  }

  function reset() {
    onChange({ pair: "", outcome: "", dateFrom: "", dateTo: "" });
  }

  const hasActiveFilters =
    filters.pair || filters.outcome || filters.dateFrom || filters.dateTo;

  return (
    <div className="flex flex-wrap items-end gap-3">
      {/* Pair Filter */}
      <div className="flex flex-col gap-1">
        <label className="text-label text-tertiary">Pair</label>
        <select
          value={filters.pair}
          onChange={(e) => update("pair", e.target.value)}
          className={selectClasses}
        >
          <option value="">All Pairs</option>
          {PAIRS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </div>

      {/* Outcome Filter */}
      <div className="flex flex-col gap-1">
        <label className="text-label text-tertiary">Outcome</label>
        <select
          value={filters.outcome}
          onChange={(e) => update("outcome", e.target.value)}
          className={selectClasses}
        >
          <option value="">All Outcomes</option>
          {OUTCOMES.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </div>

      {/* Date From */}
      <div className="flex flex-col gap-1">
        <label className="text-label text-tertiary">From</label>
        <input
          type="date"
          value={filters.dateFrom}
          onChange={(e) => update("dateFrom", e.target.value)}
          className={inputClasses}
        />
      </div>

      {/* Date To */}
      <div className="flex flex-col gap-1">
        <label className="text-label text-tertiary">To</label>
        <input
          type="date"
          value={filters.dateTo}
          onChange={(e) => update("dateTo", e.target.value)}
          className={inputClasses}
        />
      </div>

      {/* Reset */}
      {hasActiveFilters && (
        <button
          onClick={reset}
          className="flex items-center gap-1 text-xs text-accent hover:underline pb-2"
          aria-label="Reset filters"
        >
          <RotateCcw size={12} />
          Reset
        </button>
      )}
    </div>
  );
}

export type { TradeFiltersData };
