"use client";

import { useEffect, useRef } from "react";
import { useAccount } from "@/hooks/useAccount";
import { AlertTriangle, TrendingUp, TrendingDown, Wallet } from "lucide-react";
import {
  motion,
  AnimatePresence,
  useMotionValue,
  useTransform,
  animate,
} from "motion/react";

/* ── Animated number ───────────────────────────────────────── */

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
      duration: 0.7,
      ease: [0.16, 1, 0.3, 1],
    });
    prevValue.current = value;
    return () => controls.stop();
  }, [value, mv]);

  return <motion.span className={className}>{display}</motion.span>;
}

/* ── Stagger variants ──────────────────────────────────────── */

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.05 },
  },
};

const childVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as const },
  },
} as const;

/* ── Trend arrow ───────────────────────────────────────────── */

function TrendArrow({ isProfit }: { isProfit: boolean }) {
  return (
    <AnimatePresence mode="wait">
      <motion.span
        key={isProfit ? "up" : "down"}
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0, opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="inline-flex"
      >
        {isProfit ? (
          <TrendingUp className="w-4 h-4 text-profit" />
        ) : (
          <TrendingDown className="w-4 h-4 text-loss" />
        )}
      </motion.span>
    </AnimatePresence>
  );
}

/* ── Mode badge ────────────────────────────────────────────── */

function ModeBadge({ mode }: { mode: "PAPER" | "LIVE" }) {
  const isLive = mode === "LIVE";
  return (
    <span
      className="relative inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wider"
      style={{
        background: isLive
          ? "rgba(0, 200, 150, 0.12)"
          : "rgba(255, 179, 71, 0.12)",
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

/* ── AccountPanel — Hero Card ──────────────────────────────── */

export default function AccountPanel() {
  const { account, loading, error } = useAccount();

  if (loading) {
    return (
      <div className="glass-hero p-7 h-[220px]">
        <div className="animate-pulse space-y-4">
          <div className="h-3 w-20 rounded bg-elevated" />
          <div className="h-10 w-48 rounded bg-elevated" />
          <div className="h-3 w-32 rounded bg-elevated" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-hero p-7 h-[220px] flex items-center gap-3 text-loss">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <p className="text-sm">Failed to load account: {error}</p>
      </div>
    );
  }

  if (!account) return <div className="glass-hero p-7 animate-pulse h-[220px]" />;

  const balance = parseFloat(account.balance || "0");
  const equity = parseFloat(account.equity || "0");
  const unrealizedPnl = parseFloat(account.unrealized_pnl || "0");
  const dailyPnl = parseFloat(account.daily_pnl_usd || "0");
  const isProfit = unrealizedPnl >= 0;
  const isDailyProfit = dailyPnl >= 0;

  return (
    <motion.div
      className="glass-hero p-7 h-full"
      aria-live="polite"
      aria-atomic="true"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header row */}
      <motion.div
        className="flex items-center justify-between mb-5"
        variants={childVariants}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: "var(--gradient-accent-subtle)" }}
          >
            <Wallet size={16} style={{ color: "var(--color-accent)" }} />
          </div>
          <span className="text-label" style={{ color: "var(--color-text-tertiary)" }}>
            Account Balance
          </span>
        </div>
        <ModeBadge mode={account.mode} />
      </motion.div>

      {/* Hero balance — large and prominent */}
      <motion.div className="mb-2" variants={childVariants}>
        <p className="text-metric-lg" style={{ color: "var(--color-text-primary)" }}>
          <AnimatedNumber value={balance} prefix="$" />
        </p>
      </motion.div>

      {/* Equity subtitle */}
      <motion.p
        className="text-sm mb-5"
        style={{ color: "var(--color-text-secondary)" }}
        variants={childVariants}
      >
        Equity:{" "}
        <AnimatedNumber
          value={equity}
          prefix="$"
          className="font-mono font-medium"
        />
        <span className="mx-2 opacity-30">|</span>
        Open: <span className="font-mono font-medium">{account.open_trade_count}</span>
      </motion.p>

      {/* P&L row — separated with subtle divider */}
      <motion.div
        className="pt-4 grid grid-cols-2 gap-4"
        style={{ borderTop: "1px solid rgba(30, 55, 92, 0.25)" }}
        variants={childVariants}
      >
        <div>
          <p className="text-label mb-1.5" style={{ color: "var(--color-text-tertiary)" }}>
            Unrealized P&L
          </p>
          <div className="flex items-center gap-2">
            <TrendArrow isProfit={isProfit} />
            <AnimatedNumber
              value={unrealizedPnl}
              prefix="$"
              showSign
              className={`text-lg font-mono font-bold ${
                isProfit ? "text-profit" : "text-loss"
              }`}
            />
          </div>
        </div>
        <div>
          <p className="text-label mb-1.5" style={{ color: "var(--color-text-tertiary)" }}>
            Daily P&L
          </p>
          <div className="flex items-center gap-2">
            <TrendArrow isProfit={isDailyProfit} />
            <AnimatedNumber
              value={dailyPnl}
              prefix="$"
              showSign
              className={`text-lg font-mono font-bold ${
                isDailyProfit ? "text-profit" : "text-loss"
              }`}
            />
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
