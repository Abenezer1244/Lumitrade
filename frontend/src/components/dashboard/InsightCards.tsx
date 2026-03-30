"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Sparkles, ArrowUpRight, Trophy, BarChart4 } from "lucide-react";

interface Insight {
  icon: typeof Sparkles;
  title: string;
  value: string;
  color: string;
}

export default function InsightCards() {
  const [insights, setInsights] = useState<Insight[]>([]);

  useEffect(() => {
    async function fetchInsights() {
      try {
        const res = await fetch("/api/analytics/periods");
        if (!res.ok) return;
        const data = await res.json();

        // Get "All Time" stats
        const all = data?.["All Time"];
        if (!all || all.trades === 0) return;

        // Try to get pair breakdown
        let bestPair = "N/A";
        let bestPairPnl = 0;
        try {
          const pairRes = await fetch("/api/analytics");
          if (pairRes.ok) {
            const pairData = await pairRes.json();
            const pairs = pairData?.pairBreakdown || [];
            if (pairs.length > 0) {
              const sorted = [...pairs].sort((a: { pnl: number }, b: { pnl: number }) => b.pnl - a.pnl);
              bestPair = sorted[0]?.pair?.replace("_", "/") || "N/A";
              bestPairPnl = sorted[0]?.pnl || 0;
            }
          }
        } catch { /* silent */ }

        const cards: Insight[] = [];

        if (all.winRate >= 50) {
          cards.push({
            icon: Trophy,
            title: "Win Rate",
            value: `${all.winRate.toFixed(0)}% — ${all.winRate >= 60 ? "Excellent" : "Solid"} performance`,
            color: "var(--color-profit)",
          });
        }

        if (bestPair !== "N/A") {
          cards.push({
            icon: ArrowUpRight,
            title: "Best Pair",
            value: `${bestPair} — ${bestPairPnl >= 0 ? "+" : ""}$${Math.abs(bestPairPnl).toFixed(2)}`,
            color: bestPairPnl >= 0 ? "var(--color-profit)" : "var(--color-loss)",
          });
        }

        if (all.trades > 0) {
          const avgPnl = all.pnl / all.trades;
          cards.push({
            icon: BarChart4,
            title: "Avg Trade",
            value: `${avgPnl >= 0 ? "+" : ""}$${Math.abs(avgPnl).toFixed(2)} per trade`,
            color: avgPnl >= 0 ? "var(--color-profit)" : "var(--color-loss)",
          });
        }

        if (cards.length < 3) {
          cards.push({
            icon: Sparkles,
            title: "Tip",
            value: `${50 - all.trades > 0 ? `${50 - all.trades} more trades` : "Review"} to reach go/no-go gate`,
            color: "var(--color-accent)",
          });
        }

        setInsights(cards.slice(0, 3));
      } catch { /* silent */ }
    }
    fetchInsights();
  }, []);

  if (insights.length === 0) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {insights.map((insight, i) => {
        const Icon = insight.icon;
        return (
          <motion.div
            key={insight.title}
            className="glass p-4 flex items-start gap-3"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] as const }}
          >
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
              style={{ backgroundColor: `${insight.color}15` }}
            >
              <Icon size={16} style={{ color: insight.color }} />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-wider mb-0.5" style={{ color: "var(--color-text-tertiary)" }}>
                {insight.title}
              </p>
              <p className="text-sm font-medium" style={{ color: "var(--color-text-primary)" }}>
                {insight.value}
              </p>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
