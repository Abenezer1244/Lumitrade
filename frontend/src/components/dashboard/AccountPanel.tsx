"use client";

import { useAccount } from "@/hooks/useAccount";
import { AlertTriangle } from "lucide-react";

export default function AccountPanel() {
  const { account, loading, error } = useAccount();

  if (loading) return <div className="glass p-5 animate-pulse h-36" />;

  if (error) {
    return (
      <div className="glass p-5 h-36 flex items-center gap-3 text-loss">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <p className="text-sm">Failed to load account: {error}</p>
      </div>
    );
  }

  if (!account) return <div className="glass p-5 animate-pulse h-36" />;

  return (
    <div className="glass p-5" aria-live="polite" aria-atomic="true">
      <p className="text-label text-tertiary mb-2">Account</p>
      <p className="text-metric text-primary">
        ${parseFloat(account.balance).toFixed(2)}
      </p>
      <p className="text-xs text-secondary mt-1">
        Equity: ${parseFloat(account.equity || "0").toFixed(2)}
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
    </div>
  );
}
