"use client";
import { useState, useEffect } from "react";
import PnlDisplay from "@/components/ui/PnlDisplay";

interface DailyData {
  daily_pnl_usd: string;
  daily_trade_count: number;
  daily_win_rate: string;
}

export default function TodayPanel() {
  const [data, setData] = useState<DailyData | null>(null);
  useEffect(() => { fetch("/api/account").then(r => r.json()).then(setData).catch(() => {}); }, []);
  if (!data) return <div className="bg-surface border border-border rounded-lg p-5 animate-pulse h-36" />;
  return (
    <div className="bg-surface border border-border rounded-lg p-5">
      <p className="text-label text-tertiary mb-2">Today</p>
      <PnlDisplay value={data.daily_pnl_usd} size="lg" />
      <div className="flex gap-4 mt-3">
        <div><p className="text-label text-tertiary">Trades</p><p className="text-sm font-mono text-primary">{data.daily_trade_count || 0}</p></div>
        <div><p className="text-label text-tertiary">Win Rate</p><p className="text-sm font-mono text-primary">{data.daily_win_rate ? `${(parseFloat(data.daily_win_rate) * 100).toFixed(0)}%` : "---"}</p></div>
      </div>
    </div>
  );
}
