"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  NotebookPen,
  TrendingUp,
  TrendingDown,
  Target,
  Trophy,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

interface WeekSummary {
  week_start: string;
  week_end: string;
  trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl_per_trade: number;
  best_pair: string;
  worst_pair: string;
  best_trade: number;
  worst_trade: number;
  avg_confidence: number;
  tp_hit_rate: number;
  sl_hit_rate: number;
  recommendation: string;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00Z");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

function WeekCard({ week, index }: { week: WeekSummary; index: number }) {
  const [expanded, setExpanded] = useState(index === 0);
  const isProfit = week.total_pnl >= 0;

  return (
    <motion.div
      className="glass p-5"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08 }}
    >
      {/* Header */}
      <button
        className="w-full flex items-center justify-between"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: isProfit ? "var(--color-profit-dim)" : "var(--color-loss-dim)" }}
          >
            {isProfit ? (
              <TrendingUp size={18} style={{ color: "var(--color-profit)" }} />
            ) : (
              <TrendingDown size={18} style={{ color: "var(--color-loss)" }} />
            )}
          </div>
          <div className="text-left">
            <p className="text-sm font-semibold" style={{ color: "var(--color-text-primary)" }}>
              {formatDate(week.week_start)} — {formatDate(week.week_end)}
            </p>
            <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
              {week.trades} trades
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <p
              className="text-base font-mono font-bold"
              style={{ color: isProfit ? "var(--color-profit)" : "var(--color-loss)" }}
            >
              {isProfit ? "+" : ""}${week.total_pnl.toFixed(2)}
            </p>
            <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
              {week.win_rate.toFixed(0)}% WR
            </p>
          </div>
          {expanded ? (
            <ChevronUp size={16} style={{ color: "var(--color-text-tertiary)" }} />
          ) : (
            <ChevronDown size={16} style={{ color: "var(--color-text-tertiary)" }} />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          transition={{ duration: 0.2 }}
          className="mt-4 pt-4"
          style={{ borderTop: "1px solid var(--color-border)" }}
        >
          {/* Stats Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <StatBox label="Wins" value={String(week.wins)} icon={Trophy} color="var(--color-profit)" />
            <StatBox label="Losses" value={String(week.losses)} icon={AlertTriangle} color="var(--color-loss)" />
            <StatBox label="Avg/Trade" value={`$${week.avg_pnl_per_trade.toFixed(2)}`} icon={Target} color="var(--color-accent)" />
            <StatBox label="TP Hit Rate" value={`${week.tp_hit_rate.toFixed(0)}%`} icon={Target} color="var(--color-warning)" />
          </div>

          {/* Pair Performance */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="glass-elevated p-3 rounded-lg">
              <p className="text-xs mb-1" style={{ color: "var(--color-text-tertiary)" }}>Best Pair</p>
              <p className="text-sm font-mono font-semibold" style={{ color: "var(--color-profit)" }}>
                {week.best_pair.replace("_", "/")}
              </p>
            </div>
            <div className="glass-elevated p-3 rounded-lg">
              <p className="text-xs mb-1" style={{ color: "var(--color-text-tertiary)" }}>Worst Pair</p>
              <p className="text-sm font-mono font-semibold" style={{ color: "var(--color-loss)" }}>
                {week.worst_pair.replace("_", "/")}
              </p>
            </div>
          </div>

          {/* Best/Worst Trade */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="glass-elevated p-3 rounded-lg">
              <p className="text-xs mb-1" style={{ color: "var(--color-text-tertiary)" }}>Best Trade</p>
              <p className="text-sm font-mono font-bold" style={{ color: "var(--color-profit)" }}>
                +${week.best_trade.toFixed(2)}
              </p>
            </div>
            <div className="glass-elevated p-3 rounded-lg">
              <p className="text-xs mb-1" style={{ color: "var(--color-text-tertiary)" }}>Worst Trade</p>
              <p className="text-sm font-mono font-bold" style={{ color: "var(--color-loss)" }}>
                ${week.worst_trade.toFixed(2)}
              </p>
            </div>
          </div>

          {/* AI Recommendation */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: "var(--color-surface-elevated)", border: "1px solid var(--color-border)" }}>
            <div className="flex items-center gap-2 mb-2">
              <NotebookPen size={14} style={{ color: "var(--color-accent)" }} />
              <p className="text-xs font-semibold" style={{ color: "var(--color-accent)" }}>
                AI Weekly Review
              </p>
            </div>
            <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
              {week.recommendation}
            </p>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}

function StatBox({ label, value, icon: Icon, color }: { label: string; value: string; icon: typeof Trophy; color: string }) {
  return (
    <div className="glass-elevated p-3 rounded-lg">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon size={12} style={{ color }} />
        <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>{label}</p>
      </div>
      <p className="text-sm font-mono font-semibold" style={{ color: "var(--color-text-primary)" }}>{value}</p>
    </div>
  );
}

export default function JournalPage() {
  const [weeks, setWeeks] = useState<WeekSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/journal")
      .then((r) => r.json())
      .then((d) => setWeeks(d.weeks || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="glass p-5 animate-pulse h-20" />
        ))}
      </div>
    );
  }

  if (weeks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-96 gap-4">
        <div className="glass p-8 max-w-md text-center">
          <NotebookPen size={32} className="mx-auto mb-3" style={{ color: "var(--color-text-tertiary)" }} />
          <h2 className="text-lg font-semibold mb-2" style={{ color: "var(--color-text-primary)" }}>No Journal Entries Yet</h2>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Weekly summaries appear here once trades start closing. Check back after your first trading week.
          </p>
        </div>
      </div>
    );
  }

  // Overall stats
  const totalTrades = weeks.reduce((s, w) => s + w.trades, 0);
  const totalPnl = weeks.reduce((s, w) => s + w.total_pnl, 0);
  const totalWins = weeks.reduce((s, w) => s + w.wins, 0);
  const overallWr = totalTrades > 0 ? (totalWins / totalTrades) * 100 : 0;

  return (
    <div className="space-y-4">
      {/* Header Stats */}
      <div className="glass p-5">
        <div className="flex items-center gap-2 mb-4">
          <NotebookPen size={18} style={{ color: "var(--color-accent)" }} />
          <h1 className="text-lg font-semibold" style={{ color: "var(--color-text-primary)" }}>Trade Journal</h1>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>Total P&L</p>
            <p
              className="text-xl font-mono font-bold"
              style={{ color: totalPnl >= 0 ? "var(--color-profit)" : "var(--color-loss)" }}
            >
              {totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}
            </p>
          </div>
          <div>
            <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>Win Rate</p>
            <p className="text-xl font-mono font-bold" style={{ color: "var(--color-text-primary)" }}>
              {overallWr.toFixed(1)}%
            </p>
          </div>
          <div>
            <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>Total Trades</p>
            <p className="text-xl font-mono font-bold" style={{ color: "var(--color-text-primary)" }}>
              {totalTrades}
            </p>
          </div>
        </div>
      </div>

      {/* Weekly Entries */}
      {weeks.map((week, i) => (
        <WeekCard key={week.week_start} week={week} index={i} />
      ))}
    </div>
  );
}
