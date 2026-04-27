"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useAccount } from "@/hooks/useAccount";
import { AlertTriangle, TrendingUp, TrendingDown, Minus, Calendar } from "lucide-react";
import { motion, useMotionValue, useTransform, animate, AnimatePresence } from "motion/react";
import { formatSignedUsd } from "@/lib/formatters";

/* ─── Animated P&L Counter ─── */
function AnimatedPnlCounter({ value }: { value: number }) {
  const motionVal = useMotionValue(0);
  const rounded = useTransform(motionVal, (latest) => formatSignedUsd(latest));
  const [displayText, setDisplayText] = useState(() => formatSignedUsd(value));

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
function WinRateArc({ percentage, size = "sm" }: { percentage: number; size?: "sm" | "lg" }) {
  const radius = size === "lg" ? 42 : 18;
  const strokeWidth = size === "lg" ? 5 : 3.5;
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

  const svgSize = (radius + strokeWidth) * 2;
  const fontSize = size === "lg" ? "18px" : "10px";

  return (
    <svg width={svgSize} height={svgSize} viewBox={`0 0 ${svgSize} ${svgSize}`} className="shrink-0" role="img" aria-label={`Win rate: ${normalizedPct.toFixed(0)} percent`}>
      <defs>
        <linearGradient id="winArcGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#00C896" />
          <stop offset="100%" stopColor="#00A3FF" />
        </linearGradient>
      </defs>
      <circle cx={radius + strokeWidth} cy={radius + strokeWidth} r={radius} fill="none" stroke="var(--color-border)" strokeWidth={strokeWidth} />
      <motion.circle cx={radius + strokeWidth} cy={radius + strokeWidth} r={radius} fill="none" stroke={normalizedPct >= 55 ? "url(#winArcGradient)" : arcColor} strokeWidth={strokeWidth} strokeDasharray={circumference} style={{ strokeDashoffset }} strokeLinecap="round" transform={`rotate(-90 ${radius + strokeWidth} ${radius + strokeWidth})`} />
      <text x={radius + strokeWidth} y={radius + strokeWidth} textAnchor="middle" dominantBaseline="central" className="fill-current text-primary" style={{ fontSize, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700 }}>
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
      {/* Tab bar — pill style */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div
            className="w-6 h-6 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: "var(--color-accent-glow)" }}
          >
            <Calendar size={12} style={{ color: "var(--color-accent)" }} />
          </div>
          <div
            className="flex items-center gap-0.5 p-0.5 rounded-full"
            style={{ backgroundColor: "var(--color-bg-elevated)" }}
          >
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className="px-3 py-1 rounded-full text-[10px] font-semibold tracking-wide transition-all duration-200 hover:bg-[var(--color-bg-elevated)]"
              style={{
                background: tab === activeTab ? "linear-gradient(135deg, var(--color-profit), var(--color-accent))" : undefined,
                color: tab === activeTab ? "#fff" : "var(--color-text-secondary)",
                boxShadow: tab === activeTab ? "0 2px 8px rgba(37, 99, 235, 0.25)" : "none",
              }}
            >
              {tab}
            </button>
          ))}
          </div>
        </div>
        <TrendIcon className={`w-4 h-4 ${trendColor}`} aria-label={`Trend ${trendColor.includes('profit') ? 'up' : trendColor.includes('loss') ? 'down' : 'neutral'}`} />
      </div>

      {/* Animated content swap */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.15 }}
          className="flex items-center justify-between"
        >
          {/* Left side: P&L + stats */}
          <div>
            <div className="mb-3">
              <AnimatedPnlCounter value={pnlNum} />
            </div>
            <div className="flex items-center gap-5">
              <div>
                <p className="text-label text-tertiary">Trades</p>
                <p className="text-sm font-mono text-primary">{tradeCount}</p>
              </div>
              <div>
                <p className="text-label text-tertiary">Wins</p>
                <p className="text-sm font-mono text-profit">{winCount}</p>
              </div>
            </div>
          </div>

          {/* Right side: Big win rate arc */}
          <div className="flex flex-col items-center">
            <p className="text-label text-tertiary mb-1">Win Rate</p>
            {tradeCount > 0 ? (
              <WinRateArc percentage={winRate} size="lg" />
            ) : (
              <p className="text-sm font-mono text-tertiary">---</p>
            )}
          </div>
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}
