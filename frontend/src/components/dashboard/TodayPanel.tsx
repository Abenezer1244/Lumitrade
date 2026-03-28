"use client";

import { useEffect, useRef, useState } from "react";
import { useAccount } from "@/hooks/useAccount";
import { AlertTriangle, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { motion, useMotionValue, useTransform, animate, AnimatePresence } from "motion/react";

/* ── Animated P&L Counter ─────────────────────────────────── */
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
      ease: [0.16, 1, 0.3, 1],
    });
    return () => controls.stop();
  }, [value, motionVal]);

  const colorClass = value > 0 ? "text-profit" : value < 0 ? "text-loss" : "text-secondary";
  return <span className={`font-mono text-[28px] font-bold tracking-tight ${colorClass}`}>{displayText}</span>;
}

/* ── Win Rate Arc ─────────────────────────────────────────── */
function WinRateArc({ percentage }: { percentage: number }) {
  const radius = 46;
  const strokeWidth = 5;
  const circumference = 2 * Math.PI * radius;
  const normalizedPct = Math.max(0, Math.min(100, percentage));
  const strokeDashoffset = useMotionValue(circumference);

  useEffect(() => {
    const target = circumference - (normalizedPct / 100) * circumference;
    const controls = animate(strokeDashoffset, target, {
      duration: 1.2,
      ease: [0.16, 1, 0.3, 1],
      delay: 0.3,
    });
    return () => controls.stop();
  }, [normalizedPct, circumference, strokeDashoffset]);

  const arcColor =
    normalizedPct >= 55 ? "url(#winGradient)" :
    normalizedPct >= 40 ? "var(--color-warning)" :
    "var(--color-loss)";

  const svgSize = (radius + strokeWidth) * 2;

  return (
    <svg width={svgSize} height={svgSize} viewBox={`0 0 ${svgSize} ${svgSize}`} className="shrink-0">
      <defs>
        <linearGradient id="winGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#00C896" />
          <stop offset="100%" stopColor="#00A3FF" />
        </linearGradient>
      </defs>
      <circle
        cx={radius + strokeWidth}
        cy={radius + strokeWidth}
        r={radius}
        fill="none"
        stroke="rgba(30, 55, 92, 0.3)"
        strokeWidth={strokeWidth}
      />
      <motion.circle
        cx={radius + strokeWidth}
        cy={radius + strokeWidth}
        r={radius}
        fill="none"
        stroke={arcColor}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        style={{ strokeDashoffset }}
        strokeLinecap="round"
        transform={`rotate(-90 ${radius + strokeWidth} ${radius + strokeWidth})`}
      />
      <text
        x={radius + strokeWidth}
        y={radius + strokeWidth - 6}
        textAnchor="middle"
        dominantBaseline="central"
        className="fill-current"
        style={{
          fontSize: "20px",
          fontFamily: "'JetBrains Mono', monospace",
          fontWeight: 700,
          fill: "var(--color-text-primary)",
        }}
      >
        {normalizedPct.toFixed(0)}%
      </text>
      <text
        x={radius + strokeWidth}
        y={radius + strokeWidth + 12}
        textAnchor="middle"
        dominantBaseline="central"
        style={{
          fontSize: "9px",
          fontWeight: 600,
          letterSpacing: "0.08em",
          textTransform: "uppercase" as const,
          fill: "var(--color-text-tertiary)",
        }}
      >
        WIN RATE
      </text>
    </svg>
  );
}

/* ── Period Tabs ───────────────────────────────────────────── */
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

/* ── Main Panel ───────────────────────────────────────────── */
export default function TodayPanel() {
  const { account, loading, error } = useAccount();
  const [activeTab, setActiveTab] = useState<Tab>("Today");
  const [periodStats, setPeriodStats] = useState<Record<string, PeriodStats> | null>(null);

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

  if (loading) {
    return (
      <div className="glass p-6 h-[220px]">
        <div className="animate-pulse space-y-4">
          <div className="flex gap-1">
            {[1,2,3,4].map(i => <div key={i} className="h-6 w-14 rounded-full bg-elevated" />)}
          </div>
          <div className="h-8 w-32 rounded bg-elevated" />
          <div className="h-3 w-20 rounded bg-elevated" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass p-6 h-[220px] flex items-center gap-3 text-loss">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <p className="text-sm">Failed to load stats: {error}</p>
      </div>
    );
  }

  if (!account) return <div className="glass p-6 animate-pulse h-[220px]" />;

  const periodKey = PERIOD_MAP[activeTab];
  const stats = periodStats?.[periodKey];

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
      className="glass p-6 h-full relative overflow-hidden"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      aria-live="polite"
    >
      {/* Tab bar — pill style */}
      <div className="flex items-center justify-between mb-5">
        <div
          className="flex items-center gap-0.5 p-0.5 rounded-full"
          style={{ background: "rgba(18, 30, 52, 0.6)" }}
        >
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className="px-3 py-1 rounded-full text-[10px] font-semibold tracking-wide transition-all duration-200"
              style={{
                backgroundColor: tab === activeTab ? "var(--color-accent)" : "transparent",
                color: tab === activeTab ? "#fff" : "var(--color-text-tertiary)",
                boxShadow: tab === activeTab ? "0 2px 8px rgba(61, 142, 255, 0.3)" : "none",
              }}
            >
              {tab}
            </button>
          ))}
        </div>
        <TrendIcon className={`w-4 h-4 ${trendColor}`} />
      </div>

      {/* Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="flex items-end justify-between"
        >
          {/* Left: P&L + stats */}
          <div className="flex-1 min-w-0">
            <div className="mb-4">
              <AnimatedPnlCounter value={pnlNum} />
            </div>
            <div className="flex items-center gap-6">
              <div>
                <p className="text-label mb-1" style={{ color: "var(--color-text-tertiary)" }}>Trades</p>
                <p className="text-base font-mono font-semibold" style={{ color: "var(--color-text-primary)" }}>
                  {tradeCount}
                </p>
              </div>
              <div>
                <p className="text-label mb-1" style={{ color: "var(--color-text-tertiary)" }}>Wins</p>
                <p className="text-base font-mono font-semibold text-profit">{winCount}</p>
              </div>
            </div>
          </div>

          {/* Right: Win rate arc */}
          <div className="shrink-0 ml-4">
            {tradeCount > 0 ? (
              <WinRateArc percentage={winRate} />
            ) : (
              <div className="w-[102px] h-[102px] rounded-full flex items-center justify-center"
                style={{ border: "5px solid rgba(30, 55, 92, 0.3)" }}
              >
                <span className="text-sm font-mono" style={{ color: "var(--color-text-tertiary)" }}>---</span>
              </div>
            )}
          </div>
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}
