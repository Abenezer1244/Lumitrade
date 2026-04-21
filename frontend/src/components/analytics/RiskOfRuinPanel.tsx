"use client";

interface RiskOfRuinPanelProps {
  winRate: number;
  profitFactor: number;
  maxDrawdownPct: number;
}

type RiskLevel = "LOW" | "MODERATE" | "HIGH";

interface RiskConfig {
  level: RiskLevel;
  badgeClass: string;
  explanation: string;
}

function assessRisk(
  winRate: number,
  profitFactor: number
): RiskConfig {
  if (winRate >= 55 && profitFactor >= 1.5) {
    return {
      level: "LOW",
      badgeClass: "bg-profit-dim text-profit",
      explanation:
        "Your win rate and profit factor indicate a strong statistical edge. Continue following your system with disciplined risk management.",
    };
  }
  if (winRate >= 45 && profitFactor >= 1.0) {
    return {
      level: "MODERATE",
      badgeClass: "bg-warning-dim text-warning",
      explanation:
        "Your edge is present but thin. Consider reducing position sizes and tightening risk parameters until metrics improve.",
    };
  }
  return {
    level: "HIGH",
    badgeClass: "bg-loss-dim text-loss",
    explanation:
      "Current metrics suggest a high probability of significant drawdown. Review your strategy, reduce exposure, and consider pausing live trading until backtests confirm improvement.",
  };
}

export default function RiskOfRuinPanel({
  winRate,
  profitFactor,
  maxDrawdownPct,
}: RiskOfRuinPanelProps) {
  const risk = assessRisk(winRate, profitFactor);

  return (
    <div className="glass p-5">
      <h3 className="text-card-title text-secondary mb-4">Risk of Ruin</h3>

      <div className="flex flex-col items-center gap-4">
        <span
          className={`${risk.badgeClass} px-5 py-2 rounded-full text-sm font-semibold tracking-wide`}
        >
          {risk.level}
        </span>

        <p className="text-sm text-secondary text-center leading-relaxed max-w-md">
          {risk.explanation}
        </p>
      </div>

      <div className="mt-5 pt-4 border-t border-border grid grid-cols-3 gap-3 text-center">
        <div>
          <p className="text-label text-tertiary mb-1">Win Rate</p>
          <p className="text-micro text-primary">{winRate.toFixed(1)}%</p>
        </div>
        <div>
          <p className="text-label text-tertiary mb-1">Profit Factor</p>
          <p className="text-micro text-primary">{profitFactor.toFixed(2)}</p>
        </div>
        <div>
          <p className="text-label text-tertiary mb-1">Max Drawdown</p>
          <p className="text-micro text-loss">{maxDrawdownPct.toFixed(1)}%</p>
        </div>
      </div>
    </div>
  );
}
