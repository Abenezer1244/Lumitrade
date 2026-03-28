"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Radar, ChevronDown, ChevronUp } from "lucide-react";
import { useOpenPositions } from "@/hooks/useOpenPositions";
import { formatPrice, formatPnl, formatPair } from "@/lib/formatters";
import Badge from "@/components/ui/Badge";

/* ── Pulse Dot ─────────────────────────────────────────────── */

function PulseDot() {
  return (
    <span className="relative flex h-2 w-2">
      <motion.span
        className="absolute inline-flex h-full w-full rounded-full"
        style={{ backgroundColor: "var(--color-profit)" }}
        animate={{ scale: [1, 2, 1], opacity: [0.5, 0, 0.5] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
      />
      <span className="relative inline-flex h-2 w-2 rounded-full" style={{ backgroundColor: "var(--color-profit)" }} />
    </span>
  );
}

/* ── P&L Cell with flash ───────────────────────────────────── */

function PnlCell({ value }: { value: number; pair: string }) {
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
    <td className="py-2.5 px-3 font-mono relative">
      <AnimatePresence>
        {flash && (
          <motion.span
            key={flash}
            className="absolute inset-0 rounded-md"
            style={{
              backgroundColor: flash === "up" ? "var(--color-profit)" : "var(--color-loss)",
            }}
            initial={{ opacity: 0.2 }}
            animate={{ opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          />
        )}
      </AnimatePresence>
      <span className={`relative z-10 font-medium ${colorClass}`}>{formatted}</span>
    </td>
  );
}

/* ── Direction Badge ───────────────────────────────────────── */

function DirectionBadge({ direction }: { direction: string }) {
  const yOffset = direction === "BUY" ? -1.5 : 1.5;
  return (
    <motion.span
      animate={{ y: [0, yOffset, 0] }}
      transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      className="inline-block"
    >
      <Badge action={direction} />
    </motion.span>
  );
}

/* ── Empty State ───────────────────────────────────────────── */

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center text-center min-h-[200px] py-12">
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
        className="mb-4"
      >
        <Radar size={36} strokeWidth={1.5} style={{ color: "var(--color-text-tertiary)", opacity: 0.5 }} />
      </motion.div>
      <motion.p
        className="text-sm font-medium mb-1"
        style={{ color: "var(--color-text-secondary)" }}
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 3, repeat: Infinity }}
      >
        No open positions
      </motion.p>
      <p className="text-xs max-w-xs" style={{ color: "var(--color-text-tertiary)" }}>
        Positions appear here in real time when the AI opens trades.
      </p>
    </div>
  );
}

/* ── Row animation ─────────────────────────────────────────── */

const rowVariants = {
  initial: { opacity: 0, x: -16 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 16 },
};

/* ── Main Component ────────────────────────────────────────── */

const COLLAPSED_MAX = 5;

export default function OpenPositionsTable() {
  const { positions, loading } = useOpenPositions();
  const [expanded, setExpanded] = useState(false);

  const prevIdsRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    prevIdsRef.current = new Set(positions.map((p) => p.id));
  }, [positions]);

  const hasMore = positions.length > COLLAPSED_MAX;
  const displayPositions = expanded ? positions : positions.slice(0, COLLAPSED_MAX);

  if (loading) {
    return (
      <div
        className="animate-pulse h-48"
        style={{
          background: "var(--color-bg-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--card-radius)",
        }}
      />
    );
  }

  return (
    <div
      style={{
        background: "var(--color-bg-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--card-radius)",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-3.5"
        style={{ borderBottom: "1px solid rgba(30, 55, 92, 0.25)" }}
      >
        <div className="flex items-center gap-2.5">
          <h3 className="text-card-title" style={{ color: "var(--color-text-primary)" }}>
            Open Positions
          </h3>
          <span
            className="text-[11px] font-mono font-bold px-2 py-0.5 rounded-full"
            style={{
              background: positions.length > 0 ? "var(--gradient-accent-subtle)" : "var(--color-bg-elevated)",
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
            className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-full transition-colors"
            style={{
              color: "var(--color-accent)",
              background: "var(--color-accent-glow)",
            }}
          >
            {expanded ? (
              <>Show Less <ChevronUp size={12} /></>
            ) : (
              <>Show All {positions.length} <ChevronDown size={12} /></>
            )}
          </button>
        )}
      </div>

      {/* Body */}
      {!positions.length ? (
        <EmptyState />
      ) : (
        <div className="overflow-x-auto" style={{ maxHeight: expanded ? "600px" : "auto", overflowY: expanded ? "auto" : "visible" }}>
          <table className="w-full text-sm">
            <thead>
              <tr
                className="text-left text-[10px] uppercase tracking-wider"
                style={{
                  color: "var(--color-text-tertiary)",
                  background: "rgba(12, 20, 35, 0.5)",
                }}
              >
                <th className="py-2.5 px-3 font-semibold">Pair</th>
                <th className="py-2.5 px-3 font-semibold">Dir</th>
                <th className="py-2.5 px-3 font-semibold">Entry</th>
                <th className="py-2.5 px-3 font-semibold">Current</th>
                <th className="py-2.5 px-3 font-semibold">P&amp;L</th>
                <th className="py-2.5 px-3 font-semibold">Pips</th>
                <th className="py-2.5 px-3 font-semibold">SL</th>
                <th className="py-2.5 px-3 font-semibold">TP</th>
              </tr>
            </thead>
            <AnimatePresence mode="popLayout">
              <tbody>
                {displayPositions.map((p) => {
                  const pnlValue = Number(p.pnl_usd || p.live_pnl_usd || 0);
                  const pips = Number(p.live_pnl_pips || 0);
                  const pipsColor =
                    pips > 0 ? "var(--color-profit)" : pips < 0 ? "var(--color-loss)" : "var(--color-text-secondary)";

                  return (
                    <motion.tr
                      key={p.id}
                      layout
                      variants={rowVariants}
                      initial="initial"
                      animate="animate"
                      exit="exit"
                      transition={{ type: "spring", stiffness: 300, damping: 30 }}
                      className="group cursor-default transition-colors duration-150"
                      style={{ borderTop: "1px solid rgba(30, 55, 92, 0.15)" }}
                      whileHover={{
                        backgroundColor: "rgba(18, 30, 52, 0.5)",
                        transition: { duration: 0.15 },
                      }}
                    >
                      <td className="py-2.5 px-3 font-mono font-medium" style={{ color: "var(--color-text-primary)" }}>
                        {formatPair(p.pair)}
                      </td>
                      <td className="py-2.5 px-3">
                        <DirectionBadge direction={p.direction} />
                      </td>
                      <td className="py-2.5 px-3 font-mono" style={{ color: "var(--color-text-primary)" }}>
                        {formatPrice(p.entry_price, p.pair)}
                      </td>
                      <td className="py-2.5 px-3 font-mono" style={{ color: "var(--color-text-secondary)" }}>
                        {p.current_price ? formatPrice(p.current_price, p.pair) : "---"}
                      </td>
                      <PnlCell value={pnlValue} pair={p.pair} />
                      <td className="py-2.5 px-3 font-mono font-medium" style={{ color: pipsColor }}>
                        {pips > 0 ? "+" : ""}{pips.toFixed(1)}
                      </td>
                      <td className="py-2.5 px-3 font-mono">
                        <div className="flex items-center gap-1">
                          <span style={{ color: "var(--color-loss)" }}>{formatPrice(p.stop_loss, p.pair)}</span>
                          {p.direction === "BUY" && Number(p.stop_loss) > Number(p.entry_price) && (
                            <span
                              className="text-[8px] px-1 rounded font-bold"
                              style={{ backgroundColor: "var(--color-profit-dim)", color: "var(--color-profit)" }}
                            >
                              TSL
                            </span>
                          )}
                          {p.direction === "SELL" && Number(p.stop_loss) < Number(p.entry_price) && (
                            <span
                              className="text-[8px] px-1 rounded font-bold"
                              style={{ backgroundColor: "var(--color-profit-dim)", color: "var(--color-profit)" }}
                            >
                              TSL
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 font-mono" style={{ color: "var(--color-profit)" }}>
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
