"use client";

import { useState, useMemo } from "react";
import type { Trade } from "@/types/trading";
import { useTradeHistory } from "@/hooks/useTradeHistory";
import {
  formatPair,
  formatPrice,
  formatPnl,
  formatTime,
  formatDuration,
} from "@/lib/formatters";
import { History, AlertTriangle } from "lucide-react";
import Badge from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";
import TradeFilters from "@/components/trades/TradeFilters";
import ExportButton from "@/components/trades/ExportButton";
import type { TradeFiltersData } from "@/components/trades/TradeFilters";

const INITIAL_FILTERS: TradeFiltersData = {
  pair: "",
  outcome: "",
  dateFrom: "",
  dateTo: "",
};

export default function TradesPage() {
  const { trades, loading, error } = useTradeHistory({ limit: 200 });
  const [filters, setFilters] = useState<TradeFiltersData>(INITIAL_FILTERS);

  const filteredTrades = useMemo(() => {
    return trades.filter((t) => {
      if (filters.pair && formatPair(t.pair) !== filters.pair) return false;
      if (filters.outcome && t.outcome !== filters.outcome) return false;
      if (filters.dateFrom) {
        const tradeDate = new Date(t.opened_at).toISOString().slice(0, 10);
        if (tradeDate < filters.dateFrom) return false;
      }
      if (filters.dateTo) {
        const tradeDate = new Date(t.opened_at).toISOString().slice(0, 10);
        if (tradeDate > filters.dateTo) return false;
      }
      return true;
    });
  }, [trades, filters]);

  if (loading) {
    return <div className="animate-pulse h-96 glass" />;
  }

  if (error) {
    return (
      <div className="glass p-8 flex flex-col items-center gap-3 text-loss">
        <AlertTriangle className="w-8 h-8" />
        <p className="text-sm">Failed to load trade history: {error}</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-end mb-6">
        <ExportButton trades={filteredTrades} />
      </div>

      <div className="mb-4">
        <TradeFilters filters={filters} onChange={setFilters} />
      </div>

      <div className="glass p-5 overflow-x-auto">
        {!filteredTrades.length ? (
          <EmptyState
            icon={History}
            message={
              trades.length > 0
                ? "No trades match your filters."
                : "No trades yet."
            }
            description={
              trades.length > 0
                ? "Try adjusting your filters to see more results."
                : "Trade history will appear here after the system executes its first trade."
            }
          />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-label text-tertiary">
                <th className="pb-2">Time</th>
                <th className="pb-2">Pair</th>
                <th className="pb-2">Dir</th>
                <th className="pb-2">Entry</th>
                <th className="pb-2">Exit</th>
                <th className="pb-2">P&L</th>
                <th className="pb-2">Pips</th>
                <th className="pb-2">Duration</th>
                <th className="pb-2">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {filteredTrades.map((t) => {
                const { formatted, colorClass } = formatPnl(t.pnl_usd);
                return (
                  <tr
                    key={t.id}
                    className="border-t border-border hover:bg-elevated/50 transition-colors"
                  >
                    <td className="py-2 text-micro text-secondary">
                      {formatTime(t.opened_at)}
                    </td>
                    <td className="py-2 font-mono">{formatPair(t.pair)}</td>
                    <td className="py-2">
                      <Badge action={t.direction} />
                    </td>
                    <td className="py-2 font-mono">
                      {formatPrice(t.entry_price, t.pair)}
                    </td>
                    <td className="py-2 font-mono">
                      {t.exit_price
                        ? formatPrice(t.exit_price, t.pair)
                        : "\u2014"}
                    </td>
                    <td className={`py-2 font-mono ${colorClass}`}>
                      {formatted}
                    </td>
                    <td className="py-2 font-mono text-secondary">
                      {t.pnl_pips
                        ? `${parseFloat(t.pnl_pips).toFixed(1)}p`
                        : "\u2014"}
                    </td>
                    <td className="py-2 text-secondary">
                      {formatDuration(t.duration_minutes)}
                    </td>
                    <td className="py-2">
                      {t.outcome ? (
                        <span
                          className={
                            t.outcome === "WIN"
                              ? "text-profit"
                              : t.outcome === "LOSS"
                                ? "text-loss"
                                : "text-secondary"
                          }
                        >
                          {t.outcome}
                        </span>
                      ) : (
                        "\u2014"
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
