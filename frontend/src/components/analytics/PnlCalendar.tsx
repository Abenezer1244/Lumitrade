"use client";

import { useMemo, useState } from "react";
import { motion } from "motion/react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import EmptyState from "@/components/ui/EmptyState";

interface PnlCalendarProps {
  /** Equity curve data — each point has a date and cumulative equity */
  equityCurve: { date: string; equity: number }[];
}

interface DayData {
  date: string;
  dayOfMonth: number;
  pnl: number;
}

function formatUsd(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}$${Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function getPnlColor(pnl: number, maxAbsPnl: number): string {
  if (pnl === 0) return "var(--color-bg-elevated)";
  const intensity = Math.min(Math.abs(pnl) / Math.max(maxAbsPnl, 1), 1);
  if (pnl > 0) {
    const alpha = 0.15 + intensity * 0.6;
    return `rgba(0, 200, 150, ${alpha})`;
  } else {
    const alpha = 0.15 + intensity * 0.6;
    return `rgba(255, 77, 106, ${alpha})`;
  }
}

export default function PnlCalendar({ equityCurve }: PnlCalendarProps) {
  const [monthOffset, setMonthOffset] = useState(0);

  // Compute daily P&L from equity curve (consecutive difference)
  const dailyPnl = useMemo(() => {
    const map = new Map<string, number>();
    for (let i = 0; i < equityCurve.length; i++) {
      const dateStr = equityCurve[i].date?.split("T")[0];
      if (!dateStr) continue;
      const prevEquity = i > 0 ? equityCurve[i - 1].equity : equityCurve[i].equity;
      const pnl = equityCurve[i].equity - prevEquity;
      map.set(dateStr, (map.get(dateStr) || 0) + pnl);
    }
    return map;
  }, [equityCurve]);

  // Current month to display
  const targetDate = useMemo(() => {
    const d = new Date();
    d.setMonth(d.getMonth() + monthOffset);
    return d;
  }, [monthOffset]);

  const year = targetDate.getFullYear();
  const month = targetDate.getMonth();
  const monthName = targetDate.toLocaleString("en-US", { month: "long", year: "numeric" });

  // Build calendar grid
  const { days, monthPnl, maxAbsPnl } = useMemo(() => {
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDow = (firstDay.getDay() + 6) % 7; // Monday = 0

    const result: (DayData | null)[] = [];
    // Leading empty cells
    for (let i = 0; i < startDow; i++) result.push(null);

    let total = 0;
    let maxAbs = 0;

    for (let d = 1; d <= lastDay.getDate(); d++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      const pnl = dailyPnl.get(dateStr) || 0;
      total += pnl;
      if (Math.abs(pnl) > maxAbs) maxAbs = Math.abs(pnl);
      result.push({ date: dateStr, dayOfMonth: d, pnl });
    }

    return { days: result, monthPnl: total, maxAbsPnl: maxAbs };
  }, [year, month, dailyPnl]);

  if (equityCurve.length === 0) {
    return (
      <motion.div
        className="glass p-5"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h3 className="text-card-title mb-4" style={{ color: "var(--color-text-primary)" }}>
          P&L Calendar
        </h3>
        <EmptyState message="Calendar is empty." description="Each day will show net P&L as Lumitrade closes trades." />
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
      {/* Header with navigation */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-card-title" style={{ color: "var(--color-text-primary)" }}>
          P&L Calendar
        </h3>

        <div className="flex items-center gap-3">
          <span
            className="text-[11px] font-mono font-bold"
            style={{ color: monthPnl >= 0 ? "var(--color-profit)" : "var(--color-loss)" }}
          >
            {formatUsd(monthPnl)}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setMonthOffset((o) => o - 1)}
              className="w-6 h-6 flex items-center justify-center rounded"
              style={{ backgroundColor: "var(--color-bg-elevated)", color: "var(--color-text-secondary)" }}
            >
              <ChevronLeft size={14} />
            </button>
            <span className="text-xs font-medium w-[120px] text-center" style={{ color: "var(--color-text-primary)" }}>
              {monthName}
            </span>
            <button
              onClick={() => setMonthOffset((o) => Math.min(o + 1, 0))}
              disabled={monthOffset >= 0}
              className="w-6 h-6 flex items-center justify-center rounded disabled:opacity-30"
              style={{ backgroundColor: "var(--color-bg-elevated)", color: "var(--color-text-secondary)" }}
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Weekday headers */}
      <div className="grid grid-cols-7 gap-1 mb-1">
        {WEEKDAYS.map((day) => (
          <div
            key={day}
            className="text-center text-[9px] uppercase tracking-wider py-1"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            {day}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <motion.div
        className="grid grid-cols-7 gap-1"
        initial="hidden"
        animate="show"
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.01 } } }}
      >
        {days.map((day, i) =>
          day === null ? (
            <div key={`empty-${i}`} className="aspect-square" />
          ) : (
            <motion.div
              key={day.date}
              variants={{
                hidden: { opacity: 0, scale: 0.8 },
                show: { opacity: 1, scale: 1 },
              }}
              className="aspect-square rounded-md flex flex-col items-center justify-center cursor-default group relative"
              style={{ backgroundColor: getPnlColor(day.pnl, maxAbsPnl) }}
              whileHover={{ scale: 1.15, zIndex: 10 }}
              transition={{ type: "spring", stiffness: 400, damping: 25 }}
            >
              <span className="text-[10px] font-mono" style={{ color: "var(--color-text-primary)", opacity: 0.7 }}>
                {day.dayOfMonth}
              </span>
              {day.pnl !== 0 && (
                <span
                  className="text-[8px] font-mono font-bold"
                  style={{ color: day.pnl > 0 ? "var(--color-profit)" : "var(--color-loss)" }}
                >
                  {day.pnl > 0 ? "+" : ""}{day.pnl < 1000 && day.pnl > -1000 ? `$${Math.round(day.pnl)}` : formatUsd(day.pnl)}
                </span>
              )}

              {/* Tooltip on hover */}
              <div
                className="absolute -top-10 left-1/2 -translate-x-1/2 px-2 py-1 rounded text-[10px] font-mono whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20"
                style={{
                  backgroundColor: "var(--color-bg-surface-solid)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-primary)",
                }}
              >
                {day.date}: {formatUsd(day.pnl)}
              </div>
            </motion.div>
          )
        )}
      </motion.div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 mt-3 text-[9px]" style={{ color: "var(--color-text-tertiary)" }}>
        <div className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: "rgba(255, 77, 106, 0.6)" }} />
          Loss
        </div>
        <div className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: "var(--color-bg-elevated)" }} />
          No trades
        </div>
        <div className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: "rgba(0, 200, 150, 0.6)" }} />
          Profit
        </div>
      </div>
    </motion.div>
  );
}
