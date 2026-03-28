"use client";

import { useEffect, useRef } from "react";
import { useAccount } from "@/hooks/useAccount";
import { AlertTriangle, TrendingUp, TrendingDown } from "lucide-react";
import {
  motion,
  AnimatePresence,
  useMotionValue,
  useTransform,
  animate,
} from "motion/react";

/* ------------------------------------------------------------------ */
/*  Animated number display — smoothly interpolates between values     */
/* ------------------------------------------------------------------ */

interface AnimatedNumberProps {
  value: number;
  prefix?: string;
  decimals?: number;
  className?: string;
  showSign?: boolean;
}

function AnimatedNumber({
  value,
  prefix = "",
  decimals = 2,
  className = "",
  showSign = false,
}: AnimatedNumberProps) {
  const mv = useMotionValue(0);
  const display = useTransform(mv, (latest) => {
    const sign = showSign && latest >= 0 ? "+" : "";
    return `${sign}${prefix}${Math.abs(latest).toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })}`;
  });

  const prevValue = useRef(value);

  useEffect(() => {
    const controls = animate(mv, value, {
      duration: 0.6,
      ease: [0.25, 0.46, 0.45, 0.94],
    });
    prevValue.current = value;
    return () => controls.stop();
  }, [value, mv]);

  return <motion.span className={className}>{display}</motion.span>;
}

/* ------------------------------------------------------------------ */
/*  Stagger animation variants                                         */
/* ------------------------------------------------------------------ */

const containerVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.4,
      ease: [0.25, 0.46, 0.45, 0.94] as const,
      staggerChildren: 0.08,
    },
  },
} as const;

const childVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] as const },
  },
} as const;

/* ------------------------------------------------------------------ */
/*  P&L trend arrow — animates in when value changes direction         */
/* ------------------------------------------------------------------ */

interface TrendArrowProps {
  isProfit: boolean;
}

function TrendArrow({ isProfit }: TrendArrowProps) {
  return (
    <AnimatePresence mode="wait">
      <motion.span
        key={isProfit ? "up" : "down"}
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0, opacity: 0 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        className="inline-flex"
      >
        {isProfit ? (
          <TrendingUp className="w-3.5 h-3.5 text-profit" />
        ) : (
          <TrendingDown className="w-3.5 h-3.5 text-loss" />
        )}
      </motion.span>
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------------ */
/*  Mode badge — pulses when LIVE                                      */
/* ------------------------------------------------------------------ */

interface ModeBadgeProps {
  mode: "PAPER" | "LIVE";
}

function ModeBadge({ mode }: ModeBadgeProps) {
  const isLive = mode === "LIVE";
  return (
    <span className="relative inline-flex items-center">
      {isLive && (
        <motion.span
          className="absolute inset-0 rounded-sm"
          style={{ backgroundColor: "var(--color-profit)" }}
          animate={{ opacity: [0.15, 0.35, 0.15] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      <span
        className={`relative text-sm font-mono ${
          isLive ? "text-profit" : "text-warning"
        }`}
      >
        {mode}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  AccountPanel                                                       */
/* ------------------------------------------------------------------ */

export default function AccountPanel() {
  const { account, loading, error } = useAccount();

  if (loading) return <div className="glass p-5 animate-pulse h-48" />;

  if (error) {
    return (
      <div className="glass p-5 h-48 flex items-center gap-3 text-loss">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <p className="text-sm">Failed to load account: {error}</p>
      </div>
    );
  }

  if (!account) return <div className="glass p-5 animate-pulse h-48" />;

  const balance = parseFloat(account.balance || "0");
  const equity = parseFloat(account.equity || "0");
  const unrealizedPnl = parseFloat(account.unrealized_pnl || "0");
  const dailyPnl = parseFloat(account.daily_pnl_usd || "0");
  const isProfit = unrealizedPnl >= 0;
  const isDailyProfit = dailyPnl >= 0;

  return (
    <motion.div
      className="glass p-5"
      aria-live="polite"
      aria-atomic="true"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header + Balance */}
      <motion.div variants={childVariants}>
        <p className="text-label text-tertiary mb-2">Account</p>
        <p className="text-metric text-primary">
          <AnimatedNumber value={balance} prefix="$" />
        </p>
        <p className="text-xs text-secondary mt-1">
          Equity:{" "}
          <AnimatedNumber
            value={equity}
            prefix="$"
            className="font-mono"
          />
        </p>
      </motion.div>

      {/* Open trades + Mode */}
      <motion.div className="flex gap-4 mt-3" variants={childVariants}>
        <div>
          <p className="text-label text-tertiary">Open</p>
          <p className="text-sm font-mono text-primary">
            {account.open_trade_count}
          </p>
        </div>
        <div>
          <p className="text-label text-tertiary">Mode</p>
          <ModeBadge mode={account.mode} />
        </div>
      </motion.div>

      {/* Live Unrealized P&L */}
      <motion.div
        className="mt-3 pt-3 border-t border-border"
        variants={childVariants}
      >
        <div className="flex items-center justify-between">
          <p className="text-label text-tertiary">Unrealized P&amp;L</p>
          <div className="flex items-center gap-1">
            <TrendArrow isProfit={isProfit} />
            <AnimatedNumber
              value={unrealizedPnl}
              prefix="$"
              showSign
              className={`text-sm font-mono font-bold ${
                isProfit ? "text-profit" : "text-loss"
              }`}
            />
          </div>
        </div>
        <div className="flex items-center justify-between mt-1">
          <p className="text-label text-tertiary">Daily P&amp;L</p>
          <AnimatedNumber
            value={dailyPnl}
            prefix="$"
            showSign
            className={`text-sm font-mono font-bold ${
              isDailyProfit ? "text-profit" : "text-loss"
            }`}
          />
        </div>
      </motion.div>
    </motion.div>
  );
}
