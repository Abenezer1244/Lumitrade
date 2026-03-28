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

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function DashboardPage() {
  return (
    <motion.div
      className="space-y-4"
      variants={container}
      initial="hidden"
      animate="show"
    >
      {/* Row 1: Asymmetric — Account (wider) + Today + Status (compact) */}
      <motion.div
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-4"
        variants={item}
      >
        <motion.div className="md:col-span-2 lg:col-span-5" variants={item}>
          <AccountPanel />
        </motion.div>
        <motion.div className="lg:col-span-4" variants={item}>
          <TodayPanel />
        </motion.div>
        <motion.div className="lg:col-span-3" variants={item}>
          <SystemStatusPanel />
        </motion.div>
      </motion.div>

      {/* Row 2: Wider positions table + right column */}
      <motion.div
        className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start"
        variants={item}
      >
        <motion.div className="lg:col-span-8 space-y-4" variants={item}>
          <OpenPositionsTable />
          <SignalFeed limit={8} compact />
        </motion.div>

        <motion.div className="lg:col-span-4 space-y-4" variants={item}>
          <MissionControl />
          <RiskUtilization />
          <KillSwitchButton />
        </motion.div>
      </motion.div>
    </motion.div>
  );
}
