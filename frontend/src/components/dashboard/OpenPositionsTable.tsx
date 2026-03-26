"use client";
import { useRef, useEffect, useState } from "react";
import { useOpenPositions } from "@/hooks/useOpenPositions";
import { formatPrice, formatPnl, formatPair } from "@/lib/formatters";
import Badge from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";

function LiveDot() {
  return (
    <span className="relative flex h-2.5 w-2.5 ml-2">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-profit opacity-50" />
      <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-profit" />
    </span>
  );
}

function PnlCell({ value, pair }: { value: number; pair: string }) {
  const prevRef = useRef(value);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    if (value !== prevRef.current) {
      setFlash(value > prevRef.current ? "up" : "down");
      prevRef.current = value;
      const t = setTimeout(() => setFlash(null), 600);
      return () => clearTimeout(t);
    }
  }, [value]);

  const { formatted, colorClass } = formatPnl(value);
  const flashClass = flash === "up"
    ? "bg-profit/20"
    : flash === "down"
    ? "bg-loss/20"
    : "";

  return (
    <td
      className={`py-2 font-mono transition-colors duration-300 ${colorClass} ${flashClass}`}
    >
      {formatted}
    </td>
  );
}

export default function OpenPositionsTable() {
  const { positions, loading } = useOpenPositions();
  if (loading) return <div className="glass p-5 animate-pulse h-48" />;
  return (
    <div className="glass p-5">
      <div className="flex items-center mb-3">
        <h3 className="text-card-title text-primary">
          Open Positions ({positions.length})
        </h3>
        {positions.length > 0 && <LiveDot />}
        {positions.length > 0 && (
          <span className="ml-2 text-xs text-tertiary">Live</span>
        )}
      </div>
      {!positions.length ? (
        <EmptyState message="System is watching. No open positions right now." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-label text-tertiary">
                <th className="pb-2">Pair</th>
                <th className="pb-2">Dir</th>
                <th className="pb-2">Entry</th>
                <th className="pb-2">Current</th>
                <th className="pb-2">P&amp;L</th>
                <th className="pb-2">Pips</th>
                <th className="pb-2">SL</th>
                <th className="pb-2">TP</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const pnlValue = Number(p.pnl_usd || p.live_pnl_usd || 0);
                const pips = Number(p.live_pnl_pips || 0);
                const pipsColor = pips > 0 ? "text-profit" : pips < 0 ? "text-loss" : "text-secondary";
                return (
                  <tr
                    key={p.id}
                    className="border-t border-border hover:bg-elevated/50"
                  >
                    <td className="py-2 font-mono">{formatPair(p.pair)}</td>
                    <td className="py-2">
                      <Badge action={p.direction} />
                    </td>
                    <td className="py-2 font-mono">
                      {formatPrice(p.entry_price, p.pair)}
                    </td>
                    <td className="py-2 font-mono text-secondary">
                      {p.current_price
                        ? formatPrice(p.current_price, p.pair)
                        : "---"}
                    </td>
                    <PnlCell value={pnlValue} pair={p.pair} />
                    <td className={`py-2 font-mono ${pipsColor}`}>
                      {pips > 0 ? "+" : ""}
                      {pips.toFixed(1)}
                    </td>
                    <td className="py-2 font-mono text-loss">
                      {formatPrice(p.stop_loss, p.pair)}
                    </td>
                    <td className="py-2 font-mono text-profit">
                      {formatPrice(p.take_profit, p.pair)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
