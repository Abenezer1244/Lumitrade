"use client";

import { motion } from "motion/react";
import AccountPanel from "@/components/dashboard/AccountPanel";
import TodayPanel from "@/components/dashboard/TodayPanel";
import SystemStatusPanel from "@/components/dashboard/SystemStatusPanel";
import OpenPositionsTable from "@/components/dashboard/OpenPositionsTable";
import MissionControl from "@/components/dashboard/MissionControl";
import RiskUtilization from "@/components/analytics/RiskUtilization";
import { SignalFeed } from "@/components/signals/SignalFeed";
import KillSwitchButton from "@/components/dashboard/KillSwitchButton";

/* ── Staggered reveal with varied timing ────────────────── */
const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.05 },
  },
};

const heroItem = {
  hidden: { opacity: 0, y: 24, scale: 0.98 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] as const },
  },
} as const;

const supportItem = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as const },
  },
} as const;

const fadeItem = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as const },
  },
} as const;

export default function DashboardPage() {
  return (
    <motion.div
      className="space-y-5"
      variants={container}
      initial="hidden"
      animate="show"
    >
      {/* ── Row 1: Asymmetric Bento — Hero Account + Supporting Cards ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Hero card: Account — spans 5 cols, taller */}
        <motion.div className="lg:col-span-5" variants={heroItem}>
          <AccountPanel />
        </motion.div>

        {/* Today panel — spans 4 cols */}
        <motion.div className="lg:col-span-4" variants={supportItem}>
          <TodayPanel />
        </motion.div>

        {/* System status — spans 3 cols, compact */}
        <motion.div className="lg:col-span-3" variants={fadeItem}>
          <SystemStatusPanel />
        </motion.div>
      </div>

      {/* ── Row 2: Data area — wider positions + right column ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left: Positions + Signals */}
        <motion.div className="lg:col-span-8 space-y-5" variants={supportItem}>
          <OpenPositionsTable />
          <SignalFeed limit={8} compact />
        </motion.div>

        {/* Right: Mission Control + Risk + Kill Switch */}
        <motion.div className="lg:col-span-4 space-y-5" variants={fadeItem}>
          <MissionControl />
          <RiskUtilization />
          <KillSwitchButton />
        </motion.div>
      </div>
    </motion.div>
  );
}
