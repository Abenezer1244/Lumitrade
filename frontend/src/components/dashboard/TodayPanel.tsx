"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useAccount } from "@/hooks/useAccount";
import { AlertTriangle, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { motion, useMotionValue, useTransform, animate, AnimatePresence } from "motion/react";

/* ─── Animated P&L Counter ─── */
function AnimatedPnlCounter({ value }: { value: number }) {
  const motionVal = useMotionValue(0);
  const rounded = useTransform(motionVal, (latest) => {
    const sign = latest >= 0 ? "+" : "";
    return `${sign}$${Math.abs(latest).toFixed(2)}`;
  });
  const [displayText, setDisplayText] = useState(() => {
    const sign = value >= 0 ? "+" : "";
    return `${sign}$${Math.abs(value).toFixed(2)}`;
  });

  useEffect(() => {
    const unsubscribe = rounded.on("change", (v) => setDisplayText(v));
    return unsubscribe;
  }, [rounded]);

  useEffect(() => {
    const controls = animate(motionVal, value, {
      duration: 0.8,
      ease: [0.25, 0.46, 0.45, 0.94] as const,
    });
    return () => controls.stop();
  }, [value, motionVal]);

  const colorClass = value > 0 ? "text-profit" : value < 0 ? "text-loss" : "text-secondary";
  return <span className={`font-mono text-metric ${colorClass}`}>{displayText}</span>;
}

/* ─── Win Rate Arc ─── */
function WinRateArc({ percentage }: { percentage: number }) {
  const radius = 18;
  const strokeWidth = 3.5;
  const circumference = 2 * Math.PI * radius;
  const normalizedPct = Math.max(0, Math.min(100, percentage));
  const strokeDashoffset = useMotionValue(circumference);

  useEffect(() => {
    const target = circumference - (normalizedPct / 100) * circumference;
    const controls = animate(strokeDashoffset, target, {
      duration: 1.0,
      ease: [0.25, 0.46, 0.45, 0.94] as const,
      delay: 0.3,
    });
    return () => controls.stop();
  }, [normalizedPct, circumference, strokeDashoffset]);

  const arcColor =
    normalizedPct >= 55 ? "var(--color-profit)" :
    normalizedPct >= 40 ? "var(--color-warning)" :
    "var(--color-loss)";

  return (
    <svg width={44} height={44} viewBox={`0 0 ${(radius + strokeWidth) * 2} ${(radius + strokeWidth) * 2}`} className="shrink-0">
      <circle cx={radius + strokeWidth} cy={radius + strokeWidth} r={radius} fill="none" stroke="var(--color-border)" strokeWidth={strokeWidth} />
      <motion.circle cx={radius + strokeWidth} cy={radius + strokeWidth} r={radius} fill="none" stroke={arcColor} strokeWidth={strokeWidth} strokeDasharray={circumference} style={{ strokeDashoffset }} strokeLinecap="round" transform={`rotate(-90 ${radius + strokeWidth} ${radius + strokeWidth})`} />
      <text x={radius + strokeWidth} y={radius + strokeWidth} textAnchor="middle" dominantBaseline="central" className="fill-current text-primary" style={{ fontSize: "10px", fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
        {normalizedPct.toFixed(0)}%
      </text>
    </svg>
  );
}

/* ─── Period Tabs + Data ─── */
const TABS = ["Today", "Week", "Month", "All"] as const;
type Tab = (typeof TABS)[number];

interface PeriodStats {
  pnl: number;
  trades: number;
  wins: number;
  winRate: number;
}

const PERIOD_MAP: Record<Tab, string> = {
  Today: "Today",
  Week: "This Week",
  Month: "This Month",
  All: "All Time",
};

/* ─── Main Panel ─── */
export default function TodayPanel() {
  const { account, loading, error } = useAccount();
  const [activeTab, setActiveTab] = useState<Tab>("Today");
  const [periodStats, setPeriodStats] = useState<Record<string, PeriodStats> | null>(null);

  // Fetch period stats
  useEffect(() => {
    async function fetchPeriods() {
      try {
        const res = await fetch("/api/analytics/periods");
        if (!res.ok) return;
        const data = await res.json();
        setPeriodStats(data);
      } catch { /* silent */ }
    }
    fetchPeriods();
    const interval = setInterval(fetchPeriods, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="glass p-5 animate-pulse h-44" />;

  if (error) {
    return (
      <div className="glass p-5 h-44 flex items-center gap-3 text-loss">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <p className="text-sm">Failed to load stats: {error}</p>
      </div>
    );
  }

  if (!account) return <div className="glass p-5 animate-pulse h-44" />;

  // Get stats for active tab
  const periodKey = PERIOD_MAP[activeTab];
  const stats = periodStats?.[periodKey];

  // Use account data for Today, period stats for others
  const pnlNum = activeTab === "Today"
    ? (parseFloat(account.daily_pnl_usd) || 0)
    : (stats?.pnl || 0);
  const tradeCount = activeTab === "Today"
    ? (account.daily_trade_count || 0)
    : (stats?.trades || 0);
  const winCount = activeTab === "Today"
    ? (account.daily_win_count || 0)
    : (stats?.wins || 0);
  const winRate = activeTab === "Today"
    ? (account.daily_win_rate ? parseFloat(account.daily_win_rate) : 0)
    : (stats?.winRate || 0);

  const TrendIcon = pnlNum > 0 ? TrendingUp : pnlNum < 0 ? TrendingDown : Minus;
  const trendColor = pnlNum > 0 ? "text-profit" : pnlNum < 0 ? "text-loss" : "text-secondary";

  return (
    <motion.div
      className="glass p-5 relative overflow-hidden"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      aria-live="polite"
    >
      {/* Tab bar */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-0.5">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className="px-2 py-0.5 rounded text-[10px] font-medium transition-all"
              style={{
                backgroundColor: tab === activeTab ? "var(--color-accent)" : "transparent",
                color: tab === activeTab ? "#fff" : "var(--color-text-tertiary)",
              }}
            >
              {tab}
            </button>
          ))}
        </div>
        <TrendIcon className={`w-4 h-4 ${trendColor}`} />
      </div>

      {/* Animated content swap */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.15 }}
        >
          {/* P&L */}
          <div className="mb-3">
            <AnimatedPnlCounter value={pnlNum} />
          </div>

          {/* Stats row */}
          <div className="flex items-center gap-5">
            <div>
              <p className="text-label text-tertiary">Trades</p>
              <p className="text-sm font-mono text-primary">{tradeCount}</p>
            </div>
            <div>
              <p className="text-label text-tertiary">Wins</p>
              <p className="text-sm font-mono text-profit">{winCount}</p>
            </div>
            <div>
              <p className="text-label text-tertiary mb-1">Win Rate</p>
              {tradeCount > 0 ? (
                <WinRateArc percentage={winRate} />
              ) : (
                <p className="text-sm font-mono text-tertiary">---</p>
              )}
            </div>
          </div>
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}
