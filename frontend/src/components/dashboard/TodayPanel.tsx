"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useAccount } from "@/hooks/useAccount";
import { formatPnl } from "@/lib/formatters";
import { AlertTriangle, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { motion, useMotionValue, useTransform, animate } from "motion/react";

/* ─── Animated P&L Counter ─── */
interface AnimatedPnlProps {
  value: number;
}

function AnimatedPnlCounter({ value }: AnimatedPnlProps) {
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
      ease: [0.25, 0.46, 0.45, 0.94],
    });
    return () => controls.stop();
  }, [value, motionVal]);

  const colorClass = value > 0 ? "text-profit" : value < 0 ? "text-loss" : "text-secondary";

  return (
    <span className={`font-mono text-metric ${colorClass}`}>
      {displayText}
    </span>
  );
}

/* ─── Win Rate Arc ─── */
interface WinRateArcProps {
  percentage: number;
}

function WinRateArc({ percentage }: WinRateArcProps) {
  const radius = 18;
  const strokeWidth = 3.5;
  const circumference = 2 * Math.PI * radius;
  const normalizedPct = Math.max(0, Math.min(100, percentage));

  const strokeDashoffset = useMotionValue(circumference);

  useEffect(() => {
    const target = circumference - (normalizedPct / 100) * circumference;
    const controls = animate(strokeDashoffset, target, {
      duration: 1.0,
      ease: [0.25, 0.46, 0.45, 0.94],
      delay: 0.3,
    });
    return () => controls.stop();
  }, [normalizedPct, circumference, strokeDashoffset]);

  const arcColor =
    normalizedPct >= 55
      ? "var(--color-profit)"
      : normalizedPct >= 40
        ? "var(--color-warning)"
        : "var(--color-loss)";

  return (
    <div className="flex items-center gap-2">
      <svg
        width={44}
        height={44}
        viewBox={`0 0 ${(radius + strokeWidth) * 2} ${(radius + strokeWidth) * 2}`}
        className="shrink-0"
        role="img"
        aria-label={`Win rate ${normalizedPct.toFixed(0)}%`}
      >
        {/* Track */}
        <circle
          cx={radius + strokeWidth}
          cy={radius + strokeWidth}
          r={radius}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth={strokeWidth}
        />
        {/* Animated arc */}
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
        {/* Center text */}
        <text
          x={radius + strokeWidth}
          y={radius + strokeWidth}
          textAnchor="middle"
          dominantBaseline="central"
          className="fill-current text-primary"
          style={{ fontSize: "10px", fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}
        >
          {normalizedPct.toFixed(0)}%
        </text>
      </svg>
    </div>
  );
}

/* ─── Stagger container variants ─── */
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.05,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] as const },
  },
};

/* ─── Main Panel ─── */
export default function TodayPanel() {
  const { account, loading, error } = useAccount();
  const prevSignRef = useRef<"positive" | "negative" | "zero">("zero");
  const [flashColor, setFlashColor] = useState<string | null>(null);

  const pnlNum = account ? parseFloat(account.daily_pnl_usd) || 0 : 0;
  const currentSign: "positive" | "negative" | "zero" =
    pnlNum > 0 ? "positive" : pnlNum < 0 ? "negative" : "zero";

  const triggerFlash = useCallback((color: string) => {
    setFlashColor(color);
    const timer = setTimeout(() => setFlashColor(null), 600);
    return () => clearTimeout(timer);
  }, []);

  // Detect sign change and flash
  useEffect(() => {
    const prev = prevSignRef.current;
    if (prev !== currentSign && currentSign !== "zero") {
      if (
        (prev === "positive" && currentSign === "negative") ||
        (prev === "negative" && currentSign === "positive")
      ) {
        triggerFlash(
          currentSign === "positive"
            ? "var(--color-profit)"
            : "var(--color-loss)"
        );
      }
    }
    prevSignRef.current = currentSign;
  }, [currentSign, triggerFlash]);

  if (loading) return <div className="glass p-5 animate-pulse h-36" />;

  if (error) {
    return (
      <div className="glass p-5 h-36 flex items-center gap-3 text-loss">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <p className="text-sm">Failed to load daily stats: {error}</p>
      </div>
    );
  }

  if (!account) return <div className="glass p-5 animate-pulse h-36" />;

  const winRate = account.daily_win_rate ? parseFloat(account.daily_win_rate) : 0;
  const tradeCount = account.daily_trade_count || 0;

  const TrendIcon =
    pnlNum > 0 ? TrendingUp : pnlNum < 0 ? TrendingDown : Minus;
  const trendIconColor =
    pnlNum > 0 ? "text-profit" : pnlNum < 0 ? "text-loss" : "text-secondary";

  return (
    <motion.div
      className="glass p-5 relative overflow-hidden"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      aria-live="polite"
      aria-atomic="true"
    >
      {/* Background flash on sign change */}
      {flashColor && (
        <motion.div
          className="absolute inset-0 pointer-events-none"
          initial={{ opacity: 0.15 }}
          animate={{ opacity: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          style={{ backgroundColor: flashColor }}
        />
      )}

      {/* Header row */}
      <motion.div
        className="flex items-center justify-between mb-3"
        variants={itemVariants}
      >
        <p className="text-label text-tertiary">Today</p>
        <TrendIcon className={`w-4 h-4 ${trendIconColor}`} />
      </motion.div>

      {/* Large animated P&L */}
      <motion.div variants={itemVariants} className="mb-4">
        <AnimatedPnlCounter value={pnlNum} />
        {account.daily_pnl_pct && (
          <span className="text-xs font-mono text-secondary ml-2">
            {parseFloat(account.daily_pnl_pct) >= 0 ? "+" : ""}
            {parseFloat(account.daily_pnl_pct).toFixed(2)}%
          </span>
        )}
      </motion.div>

      {/* Stats row */}
      <motion.div className="flex items-center gap-5" variants={itemVariants}>
        <div>
          <p className="text-label text-tertiary">Trades</p>
          <p className="text-sm font-mono text-primary">{tradeCount}</p>
        </div>
        <div>
          <p className="text-label text-tertiary mb-1">Win Rate</p>
          {tradeCount > 0 ? (
            <WinRateArc percentage={winRate} />
          ) : (
            <p className="text-sm font-mono text-tertiary">---</p>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
