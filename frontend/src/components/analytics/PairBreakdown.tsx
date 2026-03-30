"use client";

import { motion } from "motion/react";
import { TrendingUp, TrendingDown, Clock } from "lucide-react";
import type { PairPerformance } from "@/types/system";
import EmptyState from "@/components/ui/EmptyState";

interface PairBreakdownProps {
  data: PairPerformance[];
}

function formatPair(pair: string): string {
  return pair.replace("_", "/");
}

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function formatUsd(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}$${Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const rowVariants = {
  hidden: { opacity: 0, x: -12 },
  show: { opacity: 1, x: 0, transition: { duration: 0.3 } },
};

function WinRateBar({ rate }: { rate: number }) {
  const color =
    rate >= 60 ? "var(--color-profit)" : rate >= 45 ? "var(--color-warning)" : "var(--color-loss)";

  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 rounded-full overflow-hidden flex-1"
        style={{ backgroundColor: "var(--color-bg-elevated)", maxWidth: 60 }}
      >
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(rate, 100)}%` }}
          transition={{ duration: 0.8, delay: 0.3 }}
        />
      </div>
      <span className="font-mono text-[11px] w-[36px] text-right" style={{ color }}>
        {rate.toFixed(0)}%
      </span>
    </div>
  );
}

export default function PairBreakdown({ data }: PairBreakdownProps) {
  if (!data || data.length === 0) {
    return (
      <motion.div
        className="glass p-5"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h3 className="text-card-title mb-4" style={{ color: "var(--color-text-primary)" }}>
          Performance by Pair
        </h3>
        <EmptyState message="No pair data yet." description="Lumitrade will show win rate, P&L, and trade count per instrument here." />
      </motion.div>
    );
  }

  const totalPnl = data.reduce((s, p) => s + p.total_pnl, 0);

  return (
    <motion.div
      className="glass p-5"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-card-title" style={{ color: "var(--color-text-primary)" }}>
          Performance by Pair
        </h3>
        <span
          className="text-[11px] font-mono font-bold"
          style={{ color: totalPnl >= 0 ? "var(--color-profit)" : "var(--color-loss)" }}
        >
          Total: {formatUsd(totalPnl)}
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr
              className="text-left uppercase tracking-wider"
              style={{ color: "var(--color-text-tertiary)", fontSize: "9px" }}
            >
              <th className="pb-2 px-2">Pair</th>
              <th className="pb-2 px-2 text-center">Trades</th>
              <th className="pb-2 px-2">Win Rate</th>
              <th className="pb-2 px-2 text-right">Total P&L</th>
              <th className="pb-2 px-2 text-right">Avg P&L</th>
              <th className="pb-2 px-2 text-right">Best</th>
              <th className="pb-2 px-2 text-right">Worst</th>
              <th className="pb-2 px-2 text-right">
                <Clock size={10} className="inline mr-1" style={{ opacity: 0.6 }} />
                Avg Hold
              </th>
            </tr>
          </thead>
          <motion.tbody variants={containerVariants} initial="hidden" animate="show">
            {data.map((pair) => (
              <motion.tr
                key={pair.pair}
                variants={rowVariants}
                className="group"
                style={{ borderTop: "1px solid var(--color-border)" }}
              >
                {/* Pair name */}
                <td className="py-2.5 px-2">
                  <div className="flex items-center gap-1.5">
                    {pair.total_pnl >= 0 ? (
                      <TrendingUp size={12} style={{ color: "var(--color-profit)" }} />
                    ) : (
                      <TrendingDown size={12} style={{ color: "var(--color-loss)" }} />
                    )}
                    <span className="font-mono font-bold" style={{ color: "var(--color-text-primary)" }}>
                      {formatPair(pair.pair)}
                    </span>
                  </div>
                </td>

                {/* Trade count */}
                <td className="py-2.5 px-2 text-center font-mono" style={{ color: "var(--color-text-secondary)" }}>
                  <span style={{ color: "var(--color-profit)" }}>{pair.wins}W</span>
                  {" / "}
                  <span style={{ color: "var(--color-loss)" }}>{pair.losses}L</span>
                </td>

                {/* Win rate bar */}
                <td className="py-2.5 px-2">
                  <WinRateBar rate={pair.win_rate} />
                </td>

                {/* Total P&L */}
                <td
                  className="py-2.5 px-2 text-right font-mono font-bold"
                  style={{ color: pair.total_pnl >= 0 ? "var(--color-profit)" : "var(--color-loss)" }}
                >
                  {formatUsd(pair.total_pnl)}
                </td>

                {/* Avg P&L */}
                <td
                  className="py-2.5 px-2 text-right font-mono"
                  style={{ color: pair.avg_pnl >= 0 ? "var(--color-profit)" : "var(--color-loss)" }}
                >
                  {formatUsd(pair.avg_pnl)}
                </td>

                {/* Best trade */}
                <td className="py-2.5 px-2 text-right font-mono" style={{ color: "var(--color-profit)" }}>
                  {formatUsd(pair.best_trade)}
                </td>

                {/* Worst trade */}
                <td className="py-2.5 px-2 text-right font-mono" style={{ color: "var(--color-loss)" }}>
                  {formatUsd(pair.worst_trade)}
                </td>

                {/* Avg hold time */}
                <td className="py-2.5 px-2 text-right font-mono" style={{ color: "var(--color-text-tertiary)" }}>
                  {formatDuration(pair.avg_hold_minutes)}
                </td>
              </motion.tr>
            ))}
          </motion.tbody>
        </table>
      </div>
    </motion.div>
  );
}
