"use client";

import { useEffect, useState } from "react";
import type { PerformanceSummary } from "@/types/system";
import MetricsGrid from "@/components/analytics/MetricsGrid";
import EquityCurve from "@/components/analytics/EquityCurve";
import PairBreakdown from "@/components/analytics/PairBreakdown";
import PnlCalendar from "@/components/analytics/PnlCalendar";
import PriceChart from "@/components/analytics/PriceChart";
import TradeDistribution from "@/components/analytics/TradeDistribution";
import SessionAnalysis from "@/components/analytics/SessionAnalysis";
import ConfidenceOutcome from "@/components/analytics/ConfidenceOutcome";
import RiskOfRuinPanel from "@/components/analytics/RiskOfRuinPanel";

export default function AnalyticsPage() {
  const [performance, setPerformance] = useState<PerformanceSummary | null>(
    null
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchAnalytics() {
      try {
        const res = await fetch("/api/analytics");
        if (!res.ok) return;
        const data: PerformanceSummary = await res.json();
        if (!cancelled) {
          setPerformance(data);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchAnalytics();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <div className="space-y-6">
        <MetricsGrid metrics={performance} />

        {loading ? (
          <div className="space-y-6">
            <div className="animate-pulse glass h-[370px]" />
            <div className="animate-pulse glass h-[250px]" />
          </div>
        ) : (
          <>
            <PriceChart />

            <EquityCurve data={performance?.equity_curve ?? []} />

            <PairBreakdown data={performance?.pair_breakdown ?? []} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <TradeDistribution equityCurve={performance?.equity_curve ?? []} />
              <SessionAnalysis equityCurve={performance?.equity_curve ?? []} />
            </div>

            <PnlCalendar equityCurve={performance?.equity_curve ?? []} />

            <ConfidenceOutcome />

            {performance && performance.total_trades > 0 && (
              <RiskOfRuinPanel
                winRate={performance.win_rate}
                profitFactor={performance.profit_factor}
                maxDrawdownPct={performance.max_drawdown_pct}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
