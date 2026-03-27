"use client";

import { useMemo } from "react";
import { motion } from "motion/react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";
import { BarChart3 } from "lucide-react";
import EmptyState from "@/components/ui/EmptyState";

interface TradeDistributionProps {
  equityCurve: { date: string; equity: number }[];
}

interface Bucket {
  range: string;
  count: number;
  isProfit: boolean;
}

export default function TradeDistribution({ equityCurve }: TradeDistributionProps) {
  const { buckets, totalWins, totalLosses } = useMemo(() => {
    if (equityCurve.length < 2)
      return { buckets: [], totalWins: 0, totalLosses: 0 };

    // Compute per-trade P&L from consecutive equity differences
    const pnls: number[] = [];
    for (let i = 1; i < equityCurve.length; i++) {
      const diff = equityCurve[i].equity - equityCurve[i - 1].equity;
      if (diff !== 0) pnls.push(Math.round(diff * 100) / 100);
    }

    if (pnls.length === 0) return { buckets: [], totalWins: 0, totalLosses: 0 };

    const wins = pnls.filter((p) => p > 0);
    const losses = pnls.filter((p) => p < 0);

    // Create distribution buckets
    const allAbs = pnls.map(Math.abs);
    const maxVal = Math.max(...allAbs, 1);
    const bucketSize = Math.ceil(maxVal / 8 / 50) * 50 || 100; // Round to nearest 50

    const bucketMap = new Map<string, { count: number; isProfit: boolean }>();

    for (const pnl of pnls) {
      const bucketIdx = Math.floor(Math.abs(pnl) / bucketSize);
      const lo = bucketIdx * bucketSize;
      const hi = lo + bucketSize;
      const label = pnl >= 0 ? `+$${lo}-${hi}` : `-$${lo}-${hi}`;
      const key = `${pnl >= 0 ? "+" : "-"}${lo}`;

      if (!bucketMap.has(key)) {
        bucketMap.set(key, { count: 0, isProfit: pnl >= 0 });
      }
      bucketMap.get(key)!.count++;
    }

    // Sort: losses (negative) first, then profits (positive)
    const sorted = Array.from(bucketMap.entries())
      .map(([, v]) => v)
      .sort((a, b) => {
        if (a.isProfit !== b.isProfit) return a.isProfit ? 1 : -1;
        return 0;
      });

    // Build final buckets
    const result: Bucket[] = [];
    // Loss buckets (reversed so biggest losses on left)
    const lossBuckets: Bucket[] = [];
    const winBuckets: Bucket[] = [];

    for (const pnl of losses) {
      const idx = Math.floor(Math.abs(pnl) / bucketSize);
      const lo = idx * bucketSize;
      const label = `-$${lo}`;
      const existing = lossBuckets.find((b) => b.range === label);
      if (existing) existing.count++;
      else lossBuckets.push({ range: label, count: 1, isProfit: false });
    }

    for (const pnl of wins) {
      const idx = Math.floor(pnl / bucketSize);
      const lo = idx * bucketSize;
      const label = `+$${lo}`;
      const existing = winBuckets.find((b) => b.range === label);
      if (existing) existing.count++;
      else winBuckets.push({ range: label, count: 1, isProfit: true });
    }

    lossBuckets.sort((a, b) => {
      const aVal = parseInt(a.range.replace(/[^0-9]/g, ""));
      const bVal = parseInt(b.range.replace(/[^0-9]/g, ""));
      return bVal - aVal;
    });
    winBuckets.sort((a, b) => {
      const aVal = parseInt(a.range.replace(/[^0-9]/g, ""));
      const bVal = parseInt(b.range.replace(/[^0-9]/g, ""));
      return aVal - bVal;
    });

    return {
      buckets: [...lossBuckets, ...winBuckets],
      totalWins: wins.length,
      totalLosses: losses.length,
    };
  }, [equityCurve]);

  if (buckets.length === 0) {
    return (
      <motion.div
        className="glass p-5"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h3 className="text-card-title mb-4" style={{ color: "var(--color-text-primary)" }}>
          Trade Distribution
        </h3>
        <EmptyState message="Need more closed trades to show distribution." />
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
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BarChart3 size={15} style={{ color: "var(--color-accent)" }} />
          <h3 className="text-card-title" style={{ color: "var(--color-text-primary)" }}>
            Trade Distribution
          </h3>
        </div>
        <div className="flex items-center gap-3 text-[11px]">
          <span style={{ color: "var(--color-profit)" }}>
            {totalWins} wins
          </span>
          <span style={{ color: "var(--color-loss)" }}>
            {totalLosses} losses
          </span>
        </div>
      </div>

      <motion.div
        style={{ width: "100%", height: 220 }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={buckets} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" strokeOpacity={0.3} />
            <XAxis
              dataKey="range"
              tick={{ fill: "var(--color-text-tertiary)", fontSize: 9 }}
              stroke="var(--color-border)"
              strokeOpacity={0.3}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "var(--color-text-tertiary)", fontSize: 10 }}
              stroke="var(--color-border)"
              strokeOpacity={0.3}
              tickLine={false}
              allowDecimals={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--color-bg-surface-solid)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--card-radius)",
                fontSize: "11px",
              }}
              formatter={(value) => [`${value} trades`, "Count"]}
            />
            <Bar dataKey="count" radius={[3, 3, 0, 0]} animationDuration={800}>
              {buckets.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.isProfit ? "var(--color-profit)" : "var(--color-loss)"}
                  fillOpacity={0.8}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </motion.div>
    </motion.div>
  );
}
