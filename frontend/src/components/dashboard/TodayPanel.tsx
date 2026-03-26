"use client";

import { useAccount } from "@/hooks/useAccount";
import PnlDisplay from "@/components/ui/PnlDisplay";
import { AlertTriangle } from "lucide-react";

export default function TodayPanel() {
  const { account, loading, error } = useAccount();

  if (loading) return <div className="glass p-5 animate-pulse h-36" />;

  if (error) {
    return (
      <div className="glass p-5 h-36 flex items-center gap-3 text-loss">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <p className="text-sm">Failed to load daily stats: {error}</p>
      </div>
    );
  }

  if (!account) return <div className="glass p-5 animate-pulse h-36" />;

  return (
    <div className="glass p-5" aria-live="polite" aria-atomic="true">
      <p className="text-label text-tertiary mb-2">Today</p>
      <PnlDisplay value={account.daily_pnl_usd} size="lg" />
      <div className="flex gap-4 mt-3">
        <div>
          <p className="text-label text-tertiary">Trades</p>
          <p className="text-sm font-mono text-primary">
            {account.daily_trade_count || 0}
          </p>
        </div>
        <div>
          <p className="text-label text-tertiary">Win Rate</p>
          <p className="text-sm font-mono text-primary">
            {account.daily_win_rate
              ? `${parseFloat(account.daily_win_rate).toFixed(0)}%`
              : "---"}
          </p>
        </div>
      </div>
    </div>
  );
}
