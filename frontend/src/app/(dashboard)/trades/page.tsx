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
  formatSignedUsd,
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

  // Summary stats
  const totalPnl = filteredTrades.reduce((sum, t) => sum + (parseFloat(String(t.pnl_usd)) || 0), 0);
  const wins = filteredTrades.filter(t => t.outcome === "WIN").length;
  const losses = filteredTrades.filter(t => t.outcome === "LOSS").length;
  const winRate = filteredTrades.length > 0 ? (wins / filteredTrades.length) * 100 : 0;
  const avgPnl = filteredTrades.length > 0 ? totalPnl / filteredTrades.length : 0;

  return (
    <div>
      {/* Summary Stats Row */}
      {filteredTrades.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
          {[
            { label: "Total P&L", value: formatSignedUsd(totalPnl), color: totalPnl >= 0 ? "var(--color-profit)" : "var(--color-loss)" },
            { label: "Win Rate", value: `${winRate.toFixed(1)}%`, color: winRate >= 50 ? "var(--color-profit)" : "var(--color-loss)" },
            { label: "Trades", value: `${wins}W / ${losses}L`, color: "var(--color-text-primary)" },
            { label: "Avg Trade", value: formatSignedUsd(avgPnl), color: avgPnl >= 0 ? "var(--color-profit)" : "var(--color-loss)" },
          ].map((stat) => (
            <div key={stat.label} className="glass p-4 text-center">
              <p className="text-label mb-1" style={{ color: "var(--color-text-tertiary)" }}>{stat.label}</p>
              <p className="text-lg font-mono font-bold" style={{ color: stat.color }}>{stat.value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-end mb-5">
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
                ? "No trades match your current filters."
                : "No trade history yet."
            }
            description={
              trades.length > 0
                ? "Adjust your filters above to see more results."
                : "Lumitrade will log every trade here — entry, exit, P&L, and AI reasoning."
            }
          />
        ) : (
          <table className="w-full text-sm">
            <caption className="sr-only">Trade history with outcomes</caption>
            <thead>
              <tr className="text-left text-label text-tertiary">
                <th className="pb-2 hidden md:table-cell">Time</th>
                <th className="pb-2">Pair</th>
                <th className="pb-2">Dir</th>
                <th className="pb-2 hidden md:table-cell">Entry</th>
                <th className="pb-2 hidden md:table-cell">Exit</th>
                <th className="pb-2">P&L</th>
                <th className="pb-2 hidden lg:table-cell">Pips</th>
                <th className="pb-2 hidden lg:table-cell">Duration</th>
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
                    <td className="py-2 text-micro text-secondary hidden md:table-cell">
                      {formatTime(t.opened_at)}
                    </td>
                    <td className="py-2 font-mono">{formatPair(t.pair)}</td>
                    <td className="py-2">
                      <Badge action={t.direction} />
                    </td>
                    <td className="py-2 font-mono hidden md:table-cell">
                      {formatPrice(t.entry_price, t.pair)}
                    </td>
                    <td className="py-2 font-mono hidden md:table-cell">
                      {t.exit_price
                        ? formatPrice(t.exit_price, t.pair)
                        : "\u2014"}
                    </td>
                    <td className={`py-2 font-mono ${colorClass}`}>
                      {formatted}
                    </td>
                    <td className="py-2 font-mono text-secondary hidden lg:table-cell">
                      {t.pnl_pips
                        ? `${parseFloat(t.pnl_pips).toFixed(1)}p`
                        : "\u2014"}
                    </td>
                    <td className="py-2 text-secondary hidden lg:table-cell">
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
