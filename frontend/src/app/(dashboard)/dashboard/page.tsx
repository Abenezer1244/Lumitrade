"use client";

import { motion } from "motion/react";
import AccountPanel from "@/components/dashboard/AccountPanel";
import TodayPanel from "@/components/dashboard/TodayPanel";
import SystemStatusPanel from "@/components/dashboard/SystemStatusPanel";
import OpenPositionsTable from "@/components/dashboard/OpenPositionsTable";
import MissionControl from "@/components/dashboard/MissionControl";
import PerformanceSummaryCards from "@/components/dashboard/PerformanceSummaryCards";
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
      <motion.div
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        variants={item}
      >
        <motion.div variants={item}>
          <AccountPanel />
        </motion.div>
        <motion.div variants={item}>
          <TodayPanel />
        </motion.div>
        <motion.div variants={item}>
          <SystemStatusPanel />
        </motion.div>
      </motion.div>

      {/* Performance Summary + Market Watchlist */}
      <motion.div variants={item}>
        <PerformanceSummaryCards />
      </motion.div>
      <motion.div
        className="grid grid-cols-1 lg:grid-cols-5 gap-4"
        variants={item}
      >
        <motion.div className="lg:col-span-3" variants={item}>
          <OpenPositionsTable />
        </motion.div>
        <motion.div className="lg:col-span-2" variants={item}>
          <MissionControl />
        </motion.div>
      </motion.div>

      <motion.div
        className="grid grid-cols-1 lg:grid-cols-5 gap-4"
        variants={item}
      >
        <motion.div className="lg:col-span-3" variants={item}>
          <SignalFeed limit={8} compact />
        </motion.div>
        <motion.div className="lg:col-span-2 space-y-4" variants={item}>
          <RiskUtilization />
          <KillSwitchButton />
        </motion.div>
      </motion.div>
    </motion.div>
  );
}
