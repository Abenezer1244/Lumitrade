"use client";

import { useState, useEffect, useMemo } from "react";
import { motion } from "motion/react";
import { Brain } from "lucide-react";
import EmptyState from "@/components/ui/EmptyState";
import type { Trade as CanonicalTrade } from "@/types/trading";

type Trade = Pick<CanonicalTrade, "confidence_score" | "outcome" | "pnl_usd">;

interface ConfidenceBucket {
  range: string;
  total: number;
  wins: number;
  losses: number;
  winRate: number;
  avgPnl: number;
}

export default function ConfidenceOutcome() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchTrades() {
      try {
        const res = await fetch("/api/analytics/confidence");
        if (!res.ok) return;
        const data = await res.json();
        setTrades(data.trades || []);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    }
    fetchTrades();
  }, []);

  const buckets = useMemo(() => {
    if (trades.length === 0) return [];

    const ranges = [
      { label: "50-60%", min: 0.5, max: 0.6 },
      { label: "60-70%", min: 0.6, max: 0.7 },
      { label: "70-80%", min: 0.7, max: 0.8 },
      { label: "80-90%", min: 0.8, max: 0.9 },
      { label: "90%+", min: 0.9, max: 1.01 },
    ];

    return ranges.map((r) => {
      const inRange = trades.filter((t) => {
        const conf = Number(t.confidence_score) || 0;
        return conf >= r.min && conf < r.max;
      });
      const wins = inRange.filter((t) => t.outcome === "WIN").length;
      const losses = inRange.filter((t) => t.outcome === "LOSS").length;
      const avgPnl =
        inRange.length > 0
          ? inRange.reduce((s, t) => s + (parseFloat(t.pnl_usd || "0") || 0), 0) / inRange.length
          : 0;

      return {
        range: r.label,
        total: inRange.length,
        wins,
        losses,
        winRate: inRange.length > 0 ? (wins / inRange.length) * 100 : 0,
        avgPnl: Math.round(avgPnl * 100) / 100,
      };
    }).filter((b) => b.total > 0);
  }, [trades]);

  if (loading) {
    return <div className="glass p-5 animate-pulse h-48" />;
  }

  if (buckets.length === 0) {
    return (
      <motion.div className="glass p-5" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <h3 className="text-card-title mb-4" style={{ color: "var(--color-text-primary)" }}>
          AI Confidence vs Outcome
        </h3>
        <EmptyState message="Calibration data building." description="Lumitrade will compare AI confidence levels against actual trade outcomes." />
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
        <Brain size={15} style={{ color: "var(--color-accent)" }} />
        <h3 className="text-card-title" style={{ color: "var(--color-text-primary)" }}>
          AI Confidence vs Outcome
        </h3>
      </div>

      <p className="text-[10px] mb-3" style={{ color: "var(--color-text-tertiary)" }}>
        Does higher confidence actually lead to more wins?
      </p>

      <div className="space-y-2.5">
        {buckets.map((bucket, idx) => (
          <motion.div
            key={bucket.range}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.08 }}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-[11px] font-mono font-bold" style={{ color: "var(--color-text-primary)" }}>
                {bucket.range}
              </span>
              <div className="flex items-center gap-3 text-[10px]">
                <span style={{ color: "var(--color-text-tertiary)" }}>{bucket.total} trades</span>
                <span
                  className="font-mono font-bold"
                  style={{ color: bucket.winRate >= 50 ? "var(--color-profit)" : "var(--color-loss)" }}
                >
                  {bucket.winRate.toFixed(0)}% win
                </span>
                <span
                  className="font-mono"
                  style={{ color: bucket.avgPnl >= 0 ? "var(--color-profit)" : "var(--color-loss)" }}
                >
                  {bucket.avgPnl >= 0 ? "+" : ""}${Math.abs(bucket.avgPnl).toFixed(0)}/trade
                </span>
              </div>
            </div>
            <div className="flex h-2 rounded-full overflow-hidden" style={{ backgroundColor: "var(--color-bg-elevated)" }}>
              <motion.div
                className="h-full"
                style={{ backgroundColor: "var(--color-profit)" }}
                initial={{ width: 0 }}
                animate={{ width: `${bucket.winRate}%` }}
                transition={{ duration: 0.8, delay: 0.3 + idx * 0.1 }}
              />
              <motion.div
                className="h-full"
                style={{ backgroundColor: "var(--color-loss)" }}
                initial={{ width: 0 }}
                animate={{ width: `${100 - bucket.winRate}%` }}
                transition={{ duration: 0.8, delay: 0.3 + idx * 0.1 }}
              />
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
