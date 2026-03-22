"use client";
import { useOpenPositions } from "@/hooks/useOpenPositions";
import { formatPrice, formatPnl, formatPair } from "@/lib/formatters";
import Badge from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";

export default function OpenPositionsTable() {
  const { positions, loading } = useOpenPositions();
  if (loading) return <div className="bg-surface border border-border rounded-lg p-5 animate-pulse h-48" />;
  return (
    <div className="bg-surface border border-border rounded-lg p-5">
      <h3 className="text-card-title text-primary mb-3">Open Positions ({positions.length})</h3>
      {!positions.length ? <EmptyState message="System is watching. No open positions right now." /> : (
        <table className="w-full text-sm">
          <thead><tr className="text-left text-label text-tertiary">
            <th className="pb-2">Pair</th><th className="pb-2">Dir</th><th className="pb-2">Entry</th><th className="pb-2">P&L</th><th className="pb-2">SL</th><th className="pb-2">TP</th>
          </tr></thead>
          <tbody>{positions.map(p => {
            const { formatted, colorClass } = formatPnl(p.pnl_usd || p.live_pnl_usd);
            return (
              <tr key={p.id} className="border-t border-border hover:bg-elevated/50">
                <td className="py-2 font-mono">{formatPair(p.pair)}</td>
                <td className="py-2"><Badge action={p.direction} /></td>
                <td className="py-2 font-mono">{formatPrice(p.entry_price, p.pair)}</td>
                <td className={`py-2 font-mono ${colorClass}`}>{formatted}</td>
                <td className="py-2 font-mono text-loss">{formatPrice(p.stop_loss, p.pair)}</td>
                <td className="py-2 font-mono text-profit">{formatPrice(p.take_profit, p.pair)}</td>
              </tr>
            );
          })}</tbody>
        </table>
      )}
    </div>
  );
}
