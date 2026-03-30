"use client";

import { useEffect, useRef } from "react";
import { useAccount } from "@/hooks/useAccount";
import { AlertTriangle, ArrowUpRight, ArrowDownRight, Landmark } from "lucide-react";
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
          <ArrowUpRight className="w-3.5 h-3.5 text-profit" />
        ) : (
          <ArrowDownRight className="w-3.5 h-3.5 text-loss" />
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
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wider"
      style={{
        background: isLive ? "var(--color-profit-dim)" : "var(--color-warning-dim)",
        color: isLive ? "var(--color-profit)" : "var(--color-warning)",
      }}
    >
      {isLive && (
        <motion.span
          className="w-1.5 h-1.5 rounded-full"
          style={{ backgroundColor: "var(--color-profit)" }}
          animate={{ opacity: [1, 0.4, 1] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      {mode}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  AccountPanel                                                       */
/* ------------------------------------------------------------------ */

export default function AccountPanel() {
  const { account, loading, error } = useAccount();

  if (loading) {
    return (
      <div className="glass p-6 h-full">
        <div className="animate-pulse space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-elevated" />
              <div className="h-3 w-24 rounded bg-elevated" />
            </div>
            <div className="h-6 w-16 rounded-full bg-elevated" />
          </div>
          <div className="h-9 w-48 rounded bg-elevated" />
          <div className="h-3 w-36 rounded bg-elevated" />
          <div className="pt-4 border-t border-border grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <div className="h-2.5 w-20 rounded bg-elevated" />
              <div className="h-5 w-24 rounded bg-elevated" />
            </div>
            <div className="space-y-2">
              <div className="h-2.5 w-16 rounded bg-elevated" />
              <div className="h-5 w-20 rounded bg-elevated" />
            </div>
          </div>
        </div>
      </div>
    );
  }

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
      className="glass p-6"
      aria-live="polite"
      aria-atomic="true"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header row — icon + label + mode badge */}
      <motion.div className="flex items-center justify-between mb-4" variants={childVariants}>
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: "var(--color-accent-glow)" }}
          >
            <Landmark size={14} style={{ color: "var(--color-accent)" }} />
          </div>
          <span className="text-label" style={{ color: "var(--color-text-tertiary)" }}>
            Account Balance
          </span>
        </div>
        <ModeBadge mode={account.mode} />
      </motion.div>

      {/* Hero balance — larger */}
      <motion.div className="mb-1" variants={childVariants}>
        <p
          className="text-primary"
          style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: "32px", fontWeight: 700, letterSpacing: "-0.02em" }}
        >
          <AnimatedNumber value={balance} prefix="$" />
        </p>
      </motion.div>

      {/* Equity + Open count subtitle */}
      <motion.p className="text-sm mb-4" style={{ color: "var(--color-text-secondary)" }} variants={childVariants}>
        Equity:{" "}
        <AnimatedNumber value={equity} prefix="$" className="font-mono font-medium" />
        <span className="mx-2" style={{ opacity: 0.3 }}>|</span>
        Open: <span className="font-mono font-medium">{account.open_trade_count}</span>
      </motion.p>

      {/* P&L row — side by side */}
      <motion.div
        className="pt-4 grid grid-cols-2 gap-4"
        style={{ borderTop: "1px solid var(--color-border)" }}
        variants={childVariants}
      >
        <div>
          <p className="text-label mb-1.5" style={{ color: "var(--color-text-tertiary)" }}>
            Unrealized P&amp;L
          </p>
          <div className="flex items-center gap-1.5">
            <TrendArrow isProfit={isProfit} />
            <AnimatedNumber
              value={unrealizedPnl}
              prefix="$"
              showSign
              className={`text-base font-mono font-bold ${
                isProfit ? "text-profit" : "text-loss"
              }`}
            />
          </div>
        </div>
        <div>
          <p className="text-label mb-1.5" style={{ color: "var(--color-text-tertiary)" }}>
            Daily P&amp;L
          </p>
          <div className="flex items-center gap-1.5">
            <TrendArrow isProfit={isDailyProfit} />
            <AnimatedNumber
              value={dailyPnl}
              prefix="$"
              showSign
              className={`text-base font-mono font-bold ${
                isDailyProfit ? "text-profit" : "text-loss"
              }`}
            />
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
