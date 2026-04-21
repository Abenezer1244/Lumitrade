"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Radar, Layers } from "lucide-react";
import { useOpenPositions } from "@/hooks/useOpenPositions";
import { useAccount } from "@/hooks/useAccount";
import { formatPrice, formatPnl, formatPair } from "@/lib/formatters";
import Badge from "@/components/ui/Badge";

/* ------------------------------------------------------------------ */
/*  Animated Pulse Dot — scale + opacity breathing for live indicator  */
/* ------------------------------------------------------------------ */

function PulseDot() {
  return (
    <span className="relative flex h-2.5 w-2.5 ml-2">
      <motion.span
        className="absolute inline-flex h-full w-full rounded-full"
        style={{ backgroundColor: "var(--color-profit)" }}
        animate={{ scale: [1, 1.8, 1], opacity: [0.6, 0, 0.6] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
      />
      <span
        className="relative inline-flex h-2.5 w-2.5 rounded-full"
        style={{ backgroundColor: "var(--color-profit)" }}
      />
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  P&L Cell — flash background on value change                       */
/* ------------------------------------------------------------------ */

interface PnlCellProps {
  value: number;
  pair: string;
}

function PnlCell({ value }: PnlCellProps) {
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

  return (
    <td className="py-2 px-2 font-mono relative">
      <AnimatePresence>
        {flash && (
          <motion.span
            key={flash}
            className="absolute inset-0 rounded"
            style={{
              backgroundColor:
                flash === "up"
                  ? "var(--color-profit)"
                  : "var(--color-loss)",
            }}
            initial={{ opacity: 0.3 }}
            animate={{ opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          />
        )}
      </AnimatePresence>
      <span className={`relative z-10 ${colorClass}`}>{formatted}</span>
    </td>
  );
}

/* ------------------------------------------------------------------ */
/*  Empty state — static, no idle motion                               */
/* ------------------------------------------------------------------ */

function AnimatedEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center text-center min-h-[200px] py-12">
      <Radar
        size={40}
        strokeWidth={1.5}
        className="mb-4"
        style={{ color: "var(--color-text-tertiary)" }}
      />
      <p
        className="text-sm font-medium mb-1"
        style={{ color: "var(--color-text-secondary)" }}
      >
        No open positions.
      </p>
      <p
        className="text-xs max-w-xs"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        Positions will appear here in real time when the AI opens trades.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Row animation variants                                             */
/* ------------------------------------------------------------------ */

const rowVariants = {
  initial: { opacity: 0, x: -24 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 24 },
};

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

const COLLAPSED_MAX_ROWS = 5;

export default function OpenPositionsTable() {
  const { positions, loading } = useOpenPositions();
  const { account } = useAccount();
  const [expanded, setExpanded] = useState(false);

  // Track previous position IDs to detect removals for exit animation
  const prevIdsRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    prevIdsRef.current = new Set(positions.map((p) => p.id));
  }, [positions]);

  // Memoized count label
  const countLabel = useCallback(
    () => `Open Positions (${positions.length})`,
    [positions.length]
  );

  const hasMore = positions.length > COLLAPSED_MAX_ROWS;
  const displayPositions = expanded ? positions : positions.slice(0, COLLAPSED_MAX_ROWS);

  if (loading) {
    return (
      <div className="glass p-5 animate-pulse h-48" />
    );
  }

  return (
    <div className="glass p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div
            className="w-6 h-6 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: "var(--color-accent-glow)" }}
          >
            <Layers size={12} style={{ color: "var(--color-accent)" }} aria-hidden="true" />
          </div>
          <h3
            className="text-sm font-semibold tracking-tight"
            style={{ color: "var(--color-text-primary)" }}
          >
            Open Positions
          </h3>
          <span
            className="text-[11px] font-mono font-bold px-2 py-0.5 rounded-full"
            style={{
              background: positions.length > 0 ? "var(--color-accent-glow)" : "var(--color-bg-elevated)",
              color: positions.length > 0 ? "var(--color-accent)" : "var(--color-text-tertiary)",
            }}
          >
            {positions.length}
          </span>
          {positions.length > 0 && <PulseDot />}
        </div>
        {hasMore && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-[11px] font-medium px-2.5 py-1 rounded-full transition-colors"
            style={{
              color: "var(--color-accent)",
              backgroundColor: "var(--color-accent-glow)",
            }}
          >
            {expanded ? "Show Less" : `Show All ${positions.length}`}
          </button>
        )}
      </div>

      {/* Body */}
      {!positions.length ? (
        <AnimatedEmptyState />
      ) : (
        <div className="overflow-x-auto" style={{ maxHeight: expanded ? "600px" : "auto", overflowY: expanded ? "auto" : "visible" }}>
          <table className="w-full text-sm">
            <caption className="sr-only">Open trading positions with live P&amp;L</caption>
            <thead className="sticky top-0" style={{ backgroundColor: "var(--glass-bg-solid)", zIndex: 1 }}>
              <tr
                className="text-left text-xs uppercase tracking-wider"
                style={{ color: "var(--color-text-tertiary)" }}
              >
                <th className="pb-2 px-2">Pair</th>
                <th className="pb-2 px-2">Dir</th>
                <th className="pb-2 px-2 hidden md:table-cell">Entry</th>
                <th className="pb-2 px-2 hidden md:table-cell">Current</th>
                <th className="pb-2 px-2">P&amp;L</th>
                <th className="pb-2 px-2 hidden lg:table-cell">Pips</th>
                <th className="pb-2 px-2 hidden lg:table-cell">SL</th>
                <th className="pb-2 px-2 hidden lg:table-cell">TP</th>
              </tr>
            </thead>
            <AnimatePresence mode="popLayout">
              <tbody>
                {displayPositions.map((p) => {
                  // Use account unrealizedPnl directly when 1 position — guarantees match with Account Panel
                  const acctPnl = account ? parseFloat(account.unrealized_pnl || "0") : null;
                  const pnlValue = (positions.length === 1 && acctPnl !== null)
                    ? acctPnl
                    : (p.live_pnl_usd != null ? Number(p.live_pnl_usd) : Number(p.pnl_usd || 0));
                  const pips = Number(p.live_pnl_pips || 0);
                  const pipsColor =
                    pips > 0
                      ? "var(--color-profit)"
                      : pips < 0
                        ? "var(--color-loss)"
                        : "var(--color-text-secondary)";

                  return (
                    <motion.tr
                      key={p.id}
                      layout
                      variants={rowVariants}
                      initial="initial"
                      animate="animate"
                      exit="exit"
                      transition={{
                        type: "spring",
                        stiffness: 300,
                        damping: 30,
                      }}
                      className="group cursor-default"
                      style={{
                        borderTop: "1px solid var(--color-border)",
                      }}
                      whileHover={{
                        backgroundColor: "var(--color-bg-elevated)",
                        y: -1,
                        transition: { duration: 0.15 },
                      }}
                      whileTap={{ scale: 0.99 }}
                    >
                      <td
                        className="py-2 px-2 font-mono"
                        style={{ color: "var(--color-text-primary)" }}
                      >
                        {formatPair(p.pair)}
                      </td>
                      <td className="py-2 px-2">
                        <Badge action={p.direction} />
                      </td>
                      <td
                        className="py-2 px-2 font-mono hidden md:table-cell"
                        style={{ color: "var(--color-text-primary)" }}
                      >
                        {formatPrice(p.entry_price, p.pair)}
                      </td>
                      <td
                        className="py-2 px-2 font-mono hidden md:table-cell"
                        style={{ color: "var(--color-text-secondary)" }}
                      >
                        {p.current_price
                          ? formatPrice(p.current_price, p.pair)
                          : "---"}
                      </td>
                      <PnlCell value={pnlValue} pair={p.pair} />
                      <td
                        className="py-2 px-2 font-mono hidden lg:table-cell"
                        style={{ color: pipsColor }}
                      >
                        {pips > 0 ? "+" : ""}
                        {pips.toFixed(1)}
                      </td>
                      <td className="py-2 px-2 font-mono hidden lg:table-cell">
                        <div className="flex items-center gap-1">
                          <span style={{ color: "var(--color-loss)" }}>
                            {formatPrice(p.stop_loss, p.pair)}
                          </span>
                          {/* Trailing stop indicator: show if SL is in profit zone */}
                          {p.direction === "BUY" && Number(p.stop_loss) > Number(p.entry_price) && (
                            <motion.span
                              className="text-[8px] px-1 rounded font-bold"
                              style={{ backgroundColor: "var(--color-profit-dim)", color: "var(--color-profit)" }}
                              initial={{ scale: 0 }}
                              animate={{ scale: 1 }}
                              title="Trailing stop — profit locked"
                            >
                              TSL
                            </motion.span>
                          )}
                          {p.direction === "SELL" && Number(p.stop_loss) < Number(p.entry_price) && (
                            <motion.span
                              className="text-[8px] px-1 rounded font-bold"
                              style={{ backgroundColor: "var(--color-profit-dim)", color: "var(--color-profit)" }}
                              initial={{ scale: 0 }}
                              animate={{ scale: 1 }}
                              title="Trailing stop — profit locked"
                            >
                              TSL
                            </motion.span>
                          )}
                        </div>
                      </td>
                      <td
                        className="py-2 px-2 font-mono hidden lg:table-cell"
                        style={{ color: "var(--color-profit)" }}
                      >
                        {formatPrice(p.take_profit, p.pair)}
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </AnimatePresence>
          </table>
        </div>
      )}
    </div>
  );
}
