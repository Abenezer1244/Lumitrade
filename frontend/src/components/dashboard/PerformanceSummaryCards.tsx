"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Calendar, TrendingUp, TrendingDown } from "lucide-react";

interface PeriodStats {
  pnl: number;
  trades: number;
  wins: number;
  winRate: number;
}

const TABS = ["Today", "This Week", "This Month", "All Time"] as const;
type Tab = (typeof TABS)[number];

function formatUsd(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}$${Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function PerformanceSummaryCards() {
  const [activeTab, setActiveTab] = useState<Tab>("Today");
  const [stats, setStats] = useState<Record<Tab, PeriodStats>>({
    Today: { pnl: 0, trades: 0, wins: 0, winRate: 0 },
    "This Week": { pnl: 0, trades: 0, wins: 0, winRate: 0 },
    "This Month": { pnl: 0, trades: 0, wins: 0, winRate: 0 },
    "All Time": { pnl: 0, trades: 0, wins: 0, winRate: 0 },
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      try {
        const res = await fetch("/api/analytics/periods");
        if (!res.ok) return;
        const data = await res.json();
        setStats(data);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  const current = stats[activeTab];
  const isPositive = current.pnl >= 0;

  if (loading) {
    return (
      <div className="glass p-4 animate-pulse h-32" />
    );
  }

  return (
    <motion.div
      className="glass p-4"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Tab bar */}
      <div className="flex items-center gap-1 mb-3">
        <Calendar size={14} style={{ color: "var(--color-accent)", marginRight: 4 }} />
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className="px-2.5 py-1 rounded text-[10px] font-medium transition-all"
            style={{
              backgroundColor: tab === activeTab ? "var(--color-accent)" : "transparent",
              color: tab === activeTab ? "#fff" : "var(--color-text-tertiary)",
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Stats display */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
          className="flex items-center justify-between"
        >
          {/* P&L */}
          <div>
            <div className="flex items-center gap-2">
              {isPositive ? (
                <TrendingUp size={18} style={{ color: "var(--color-profit)" }} />
              ) : (
                <TrendingDown size={18} style={{ color: "var(--color-loss)" }} />
              )}
              <span
                className="font-mono text-xl font-bold"
                style={{ color: isPositive ? "var(--color-profit)" : "var(--color-loss)" }}
              >
                {formatUsd(current.pnl)}
              </span>
            </div>
          </div>

          {/* Trade stats */}
          <div className="flex items-center gap-4">
            <div className="text-center">
              <p className="text-[9px] uppercase tracking-wider" style={{ color: "var(--color-text-tertiary)" }}>
                Trades
              </p>
              <p className="font-mono text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
                {current.trades}
              </p>
            </div>
            <div className="text-center">
              <p className="text-[9px] uppercase tracking-wider" style={{ color: "var(--color-text-tertiary)" }}>
                Wins
              </p>
              <p className="font-mono text-sm font-bold" style={{ color: "var(--color-profit)" }}>
                {current.wins}
              </p>
            </div>
            <div className="text-center">
              <p className="text-[9px] uppercase tracking-wider" style={{ color: "var(--color-text-tertiary)" }}>
                Win Rate
              </p>
              <p
                className="font-mono text-sm font-bold"
                style={{
                  color: current.winRate >= 50 ? "var(--color-profit)" : "var(--color-loss)",
                }}
              >
                {current.winRate.toFixed(0)}%
              </p>
            </div>
          </div>
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}
