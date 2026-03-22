"use client";
import { useState, useEffect } from "react";
import PnlDisplay from "@/components/ui/PnlDisplay";
import type { AccountSummary } from "@/types/system";

export default function AccountPanel() {
  const [account, setAccount] = useState<AccountSummary | null>(null);
  useEffect(() => {
    fetch("/api/account").then(r => r.json()).then(setAccount).catch(() => {});
  }, []);
  if (!account) return <div className="bg-surface border border-border rounded-lg p-5 animate-pulse h-36" />;
  return (
    <div className="bg-surface border border-border rounded-lg p-5">
      <p className="text-label text-tertiary mb-2">Account</p>
      <p className="text-metric text-primary">${parseFloat(account.balance).toFixed(2)}</p>
      <p className="text-xs text-secondary mt-1">Equity: ${parseFloat(account.equity || "0").toFixed(2)}</p>
      <div className="flex gap-4 mt-3">
        <div><p className="text-label text-tertiary">Open</p><p className="text-sm font-mono text-primary">{account.open_trade_count}</p></div>
        <div><p className="text-label text-tertiary">Mode</p><p className={`text-sm font-mono ${account.mode === "LIVE" ? "text-profit" : "text-warning"}`}>{account.mode}</p></div>
      </div>
    </div>
  );
}
