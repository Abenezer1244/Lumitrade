"use client";

import type { PerformanceSummary } from "@/types/system";

interface MetricsGridProps {
  metrics: PerformanceSummary | null;
}

interface MetricCardConfig {
  label: string;
  getValue: (m: PerformanceSummary) => string;
  getColorClass: (m: PerformanceSummary) => string;
}

const metricCards: MetricCardConfig[] = [
  {
    label: "Total Trades",
    getValue: (m) => m.total_trades.toLocaleString(),
    getColorClass: () => "text-primary",
  },
  {
    label: "Win Rate",
    getValue: (m) => `${m.win_rate.toFixed(1)}%`,
    getColorClass: (m) => (m.win_rate >= 50 ? "text-profit" : "text-loss"),
  },
  {
    label: "Profit Factor",
    getValue: (m) => m.profit_factor.toFixed(2),
    getColorClass: (m) => {
      if (m.profit_factor >= 1.5) return "text-profit";
      if (m.profit_factor >= 1.0) return "text-warning";
      return "text-loss";
    },
  },
  {
    label: "Sharpe Ratio",
    getValue: (m) => m.sharpe_ratio.toFixed(2),
    getColorClass: () => "text-primary",
  },
  {
    label: "Avg Win",
    getValue: (m) => `${m.avg_win_pips.toFixed(1)} pips`,
    getColorClass: () => "text-profit",
  },
  {
    label: "Avg Loss",
    getValue: (m) => `${m.avg_loss_pips.toFixed(1)} pips`,
    getColorClass: () => "text-loss",
  },
  {
    label: "Max Drawdown",
    getValue: (m) => `${m.max_drawdown_pct.toFixed(1)}%`,
    getColorClass: () => "text-loss",
  },
  {
    label: "Expectancy",
    getValue: (m) =>
      `$${m.expectancy_per_trade_usd.toFixed(2)}/trade`,
    getColorClass: (m) =>
      m.expectancy_per_trade_usd >= 0 ? "text-profit" : "text-loss",
  },
];

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse glass-elevated h-24"
        />
      ))}
    </div>
  );
}

export default function MetricsGrid({ metrics }: MetricsGridProps) {
  if (!metrics) {
    return <SkeletonGrid />;
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {metricCards.map((card) => (
        <div key={card.label} className="glass p-4">
          <p className="text-label text-tertiary mb-2">{card.label}</p>
          <p className={`text-metric ${card.getColorClass(metrics)}`}>
            {card.getValue(metrics)}
          </p>
        </div>
      ))}
    </div>
  );
}
