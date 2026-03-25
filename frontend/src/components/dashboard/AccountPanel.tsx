"use client";

import { useAccount } from "@/hooks/useAccount";
import { AlertTriangle, TrendingUp, TrendingDown } from "lucide-react";

export default function AccountPanel() {
  const { account, loading, error } = useAccount();

  if (loading) return <div className="glass p-5 animate-pulse h-48" />;

  if (error) {
    return (
      <div className="glass p-5 h-48 flex items-center gap-3 text-loss">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <p className="text-sm">Failed to load account: {error}</p>
      </div>
    );
  }

  if (!account) return <div className="glass p-5 animate-pulse h-48" />;

  const balance = parseFloat(account.balance || "0");
  const equity = parseFloat(account.equity || "0");
  const unrealizedPnl = equity - balance;
  const dailyPnl = parseFloat(account.daily_pnl_usd || "0");
  const isProfit = unrealizedPnl >= 0;
  const isDailyProfit = dailyPnl >= 0;

  return (
    <div className="glass p-5" aria-live="polite" aria-atomic="true">
      <p className="text-label text-tertiary mb-2">Account</p>
      <p className="text-metric text-primary">
        ${balance.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </p>
      <p className="text-xs text-secondary mt-1">
        Equity: ${equity.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </p>
      <div className="flex gap-4 mt-3">
        <div>
          <p className="text-label text-tertiary">Open</p>
          <p className="text-sm font-mono text-primary">
            {account.open_trade_count}
          </p>
        </div>
        <div>
          <p className="text-label text-tertiary">Mode</p>
          <p
            className={`text-sm font-mono ${
              account.mode === "LIVE" ? "text-profit" : "text-warning"
            }`}
          >
            {account.mode}
          </p>
        </div>
      </div>

      {/* Live Unrealized P&L */}
      <div className="mt-3 pt-3 border-t border-border">
        <div className="flex items-center justify-between">
          <p className="text-label text-tertiary">Unrealized P&L</p>
          <div className="flex items-center gap-1">
            {isProfit ? (
              <TrendingUp className="w-3.5 h-3.5 text-profit" />
            ) : (
              <TrendingDown className="w-3.5 h-3.5 text-loss" />
            )}
            <p className={`text-sm font-mono font-bold ${isProfit ? "text-profit" : "text-loss"}`}>
              {isProfit ? "+" : ""}${unrealizedPnl.toFixed(2)}
            </p>
          </div>
        </div>
        <div className="flex items-center justify-between mt-1">
          <p className="text-label text-tertiary">Daily P&L</p>
          <p className={`text-sm font-mono font-bold ${isDailyProfit ? "text-profit" : "text-loss"}`}>
            {isDailyProfit ? "+" : ""}${dailyPnl.toFixed(2)}
          </p>
        </div>
      </div>
    </div>
  );
}
