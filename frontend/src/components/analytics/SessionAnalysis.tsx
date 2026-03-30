"use client";

import { useMemo } from "react";
import { motion } from "motion/react";
import { Clock } from "lucide-react";
import EmptyState from "@/components/ui/EmptyState";

interface SessionAnalysisProps {
  equityCurve: { date: string; equity: number }[];
}

interface SessionStats {
  name: string;
  hours: string;
  pnl: number;
  trades: number;
  color: string;
}

const SESSIONS = [
  { name: "Sydney", startHour: 22, endHour: 7, color: "var(--color-accent)" },
  { name: "Tokyo", startHour: 0, endHour: 9, color: "#9B7ED8" },
  { name: "London", startHour: 8, endHour: 17, color: "#3D8EFF" },
  { name: "New York", startHour: 13, endHour: 22, color: "#FFB347" },
  { name: "Overlap", startHour: 13, endHour: 17, color: "var(--color-profit)" },
];

function getSession(hour: number): string {
  if (hour >= 13 && hour < 17) return "Overlap";
  if (hour >= 8 && hour < 13) return "London";
  if (hour >= 17 && hour < 22) return "New York";
  if (hour >= 0 && hour < 9) return "Tokyo";
  return "Sydney";
}

function formatUsd(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}$${Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

export default function SessionAnalysis({ equityCurve }: SessionAnalysisProps) {
  const sessions = useMemo(() => {
    if (equityCurve.length < 2) return [];

    const sessionMap = new Map<string, { pnl: number; trades: number }>();
    for (const s of SESSIONS) {
      sessionMap.set(s.name, { pnl: 0, trades: 0 });
    }

    for (let i = 1; i < equityCurve.length; i++) {
      const diff = equityCurve[i].equity - equityCurve[i - 1].equity;
      if (diff === 0) continue;
      const date = equityCurve[i].date;
      if (!date) continue;
      const hour = new Date(date).getUTCHours();
      const session = getSession(hour);
      const entry = sessionMap.get(session);
      if (entry) {
        entry.pnl += diff;
        entry.trades++;
      }
    }

    return SESSIONS.map((s) => {
      const stats = sessionMap.get(s.name) || { pnl: 0, trades: 0 };
      return {
        name: s.name,
        hours: `${s.startHour.toString().padStart(2, "0")}:00-${s.endHour.toString().padStart(2, "0")}:00`,
        pnl: Math.round(stats.pnl * 100) / 100,
        trades: stats.trades,
        color: s.color,
      };
    }).filter((s) => s.trades > 0);
  }, [equityCurve]);

  const maxAbsPnl = Math.max(...sessions.map((s) => Math.abs(s.pnl)), 1);

  if (sessions.length === 0) {
    return (
      <motion.div
        className="glass p-5"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h3 className="text-card-title mb-4" style={{ color: "var(--color-text-primary)" }}>
          Session Performance
        </h3>
        <EmptyState message="Session data building up." description="Lumitrade tracks performance across Tokyo, London, and New York sessions." />
      </motion.div>
    );
  }

  return (
    <motion.div
      className="glass p-5"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex items-center gap-2 mb-4">
        <Clock size={15} style={{ color: "var(--color-accent)" }} />
        <h3 className="text-card-title" style={{ color: "var(--color-text-primary)" }}>
          Session Performance
        </h3>
      </div>

      <div className="space-y-3">
        {sessions.map((session, idx) => {
          const barWidth = Math.abs(session.pnl) / maxAbsPnl * 100;
          const isProfit = session.pnl >= 0;

          return (
            <motion.div
              key={session.name}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.08 }}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: session.color }}
                  />
                  <span className="text-[11px] font-medium" style={{ color: "var(--color-text-primary)" }}>
                    {session.name}
                  </span>
                  <span className="text-[9px] font-mono" style={{ color: "var(--color-text-tertiary)" }}>
                    {session.hours} UTC
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] font-mono" style={{ color: "var(--color-text-tertiary)" }}>
                    {session.trades} trades
                  </span>
                  <span
                    className="text-[11px] font-mono font-bold w-[80px] text-right"
                    style={{ color: isProfit ? "var(--color-profit)" : "var(--color-loss)" }}
                  >
                    {formatUsd(session.pnl)}
                  </span>
                </div>
              </div>
              <div
                className="h-1.5 rounded-full overflow-hidden"
                style={{ backgroundColor: "var(--color-bg-elevated)" }}
              >
                <motion.div
                  className="h-full rounded-full"
                  style={{
                    backgroundColor: isProfit ? "var(--color-profit)" : "var(--color-loss)",
                  }}
                  initial={{ width: 0 }}
                  animate={{ width: `${barWidth}%` }}
                  transition={{ duration: 0.8, delay: 0.3 + idx * 0.1 }}
                />
              </div>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}
