"use client";
import { useState, useEffect } from "react";
import type { Trade } from "@/types/trading";
import { formatPair, formatPrice, formatPnl, formatTime, formatDuration } from "@/lib/formatters";
import Badge from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { fetch("/api/trades").then(r => r.json()).then(d => { setTrades(d.trades || []); setLoading(false); }).catch(() => setLoading(false)); }, []);
  if (loading) return <div className="animate-pulse h-96 bg-surface rounded-lg" />;
  return (
    <div>
      <h1 className="text-display text-primary mb-6">Trade History</h1>
      <div className="bg-surface border border-border rounded-lg p-5">
        {!trades.length ? <EmptyState message="No trades yet." /> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left text-label text-tertiary"><th className="pb-2">Time</th><th className="pb-2">Pair</th><th className="pb-2">Dir</th><th className="pb-2">Entry</th><th className="pb-2">Exit</th><th className="pb-2">P&L</th><th className="pb-2">Pips</th><th className="pb-2">Duration</th><th className="pb-2">Outcome</th></tr></thead>
            <tbody>{trades.map(t => {
              const { formatted, colorClass } = formatPnl(t.pnl_usd);
              return (
                <tr key={t.id} className="border-t border-border hover:bg-elevated/50">
                  <td className="py-2 text-micro text-secondary">{formatTime(t.opened_at)}</td>
                  <td className="py-2 font-mono">{formatPair(t.pair)}</td>
                  <td className="py-2"><Badge action={t.direction} /></td>
                  <td className="py-2 font-mono">{formatPrice(t.entry_price, t.pair)}</td>
                  <td className="py-2 font-mono">{t.exit_price ? formatPrice(t.exit_price, t.pair) : "\u2014"}</td>
                  <td className={`py-2 font-mono ${colorClass}`}>{formatted}</td>
                  <td className="py-2 font-mono text-secondary">{t.pnl_pips ? `${parseFloat(t.pnl_pips).toFixed(1)}p` : "\u2014"}</td>
                  <td className="py-2 text-secondary">{formatDuration(t.duration_minutes)}</td>
                  <td className="py-2">{t.outcome ? <span className={t.outcome === "WIN" ? "text-profit" : t.outcome === "LOSS" ? "text-loss" : "text-secondary"}>{t.outcome}</span> : "\u2014"}</td>
                </tr>
              );
            })}</tbody>
          </table>
        )}
      </div>
    </div>
  );
}
