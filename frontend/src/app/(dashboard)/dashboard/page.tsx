"use client";

import { motion } from "motion/react";
import { Target } from "lucide-react";
import AccountPanel from "@/components/dashboard/AccountPanel";
import TodayPanel from "@/components/dashboard/TodayPanel";
import SystemStatusPanel from "@/components/dashboard/SystemStatusPanel";
import OpenPositionsTable from "@/components/dashboard/OpenPositionsTable";
import MissionControl from "@/components/dashboard/MissionControl";
import RiskUtilization from "@/components/analytics/RiskUtilization";
import { SignalFeed } from "@/components/signals/SignalFeed";
import KillSwitchButton from "@/components/dashboard/KillSwitchButton";
import InsightCards from "@/components/dashboard/InsightCards";
import { useAccount } from "@/hooks/useAccount";

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.05 },
  },
};

const heroItem = {
  hidden: { opacity: 0, y: 24, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] as const } },
} as const;

const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as const } },
} as const;

/* ── Greeting based on time of day ──────────────────────── */
function getGreeting(): string {
  const h = new Date().getUTCHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function formatDate(): string {
  return new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

/* ── Trade milestone progress ───────────────────────────── */
function TradeProgress({ count }: { count: number }) {
  const goal = 50;
  const pct = Math.min((count / goal) * 100, 100);
  const done = count >= goal;

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1.5">
        <Target size={14} style={{ color: done ? "var(--color-profit)" : "var(--color-accent)" }} />
        <span className="text-xs font-mono" style={{ color: "var(--color-text-secondary)" }}>
          <span className="font-bold" style={{ color: done ? "var(--color-profit)" : "var(--color-text-primary)" }}>
            {count}
          </span>
          /{goal} trades
        </span>
      </div>
      <div
        className="w-24 h-1.5 rounded-full overflow-hidden"
        style={{ backgroundColor: "var(--color-bg-elevated)" }}
      >
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: done ? "var(--color-profit)" : "var(--color-accent)" }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
      {done && (
        <span className="text-[10px] font-bold text-profit">Go/No-Go Ready</span>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const { account } = useAccount();
  const totalTrades = account?.daily_trade_count ?? 0;

  return (
    <motion.div
      className="space-y-5"
      variants={container}
      initial="hidden"
      animate="show"
    >
      {/* Greeting header */}
      <motion.div
        className="flex items-end justify-between"
        variants={item}
      >
        <div>
          <h1
            className="text-2xl font-bold mb-1"
            style={{ fontFamily: "'PT Serif', serif", color: "var(--color-text-primary)" }}
          >
            {getGreeting()}, Trader
          </h1>
          <p className="text-sm" style={{ color: "var(--color-text-tertiary)" }}>
            {formatDate()}
          </p>
        </div>
        <TradeProgress count={totalTrades} />
      </motion.div>

      {/* Row 1: Asymmetric — Account (wider) + Today + Status (compact) */}
      <motion.div
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-5 items-stretch"
        variants={item}
      >
        <motion.div className="md:col-span-2 lg:col-span-5" variants={heroItem}>
          <AccountPanel />
        </motion.div>
        <motion.div className="lg:col-span-4" variants={item}>
          <TodayPanel />
        </motion.div>
        <motion.div className="lg:col-span-3" variants={item}>
          <SystemStatusPanel />
        </motion.div>
      </motion.div>

      {/* AI Insight Cards */}
      <motion.div variants={item}>
        <InsightCards />
      </motion.div>

      {/* Row 2: Wider positions table + right column */}
      <motion.div
        className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start"
        variants={item}
      >
        <motion.div className="lg:col-span-8 space-y-5" variants={item}>
          <OpenPositionsTable />
          <SignalFeed limit={8} compact />
        </motion.div>

        <motion.div className="lg:col-span-4 space-y-5" variants={item}>
          <MissionControl />
          <RiskUtilization />
          <KillSwitchButton />
        </motion.div>
      </motion.div>
    </motion.div>
  );
}
