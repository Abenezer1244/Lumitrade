"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "motion/react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface PairPrice {
  pair: string;
  bid: number;
  ask: number;
  mid: number;
  prevMid?: number;
}

const PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD", "USD_CAD", "NZD_USD", "XAU_USD"];

function formatPair(pair: string): string {
  return pair.replace("_", "/");
}

function formatPrice(price: number, pair: string): string {
  if (pair.includes("JPY")) return price.toFixed(3);
  if (pair.includes("XAU")) return price.toFixed(2);
  return price.toFixed(5);
}

function formatSpread(bid: number, ask: number, pair: string): string {
  const pipSize = pair.includes("JPY") || pair.includes("XAU") ? 0.01 : 0.0001;
  const spread = (ask - bid) / pipSize;
  return spread.toFixed(1);
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};

const itemVariants = {
  hidden: { opacity: 0, scale: 0.95 },
  show: { opacity: 1, scale: 1 },
};

export default function MarketWatchlist() {
  const [prices, setPrices] = useState<Map<string, PairPrice>>(new Map());
  const [loading, setLoading] = useState(true);

  const fetchPrices = useCallback(async () => {
    try {
      const res = await fetch(`/api/prices?pairs=${PAIRS.join(",")}`);
      if (!res.ok) return;
      const data = await res.json();

      setPrices((prev) => {
        const next = new Map(prev);
        for (const [pair, info] of Object.entries(data.prices || {})) {
          const p = info as { bid: number; ask: number; mid: number };
          const prevEntry = prev.get(pair);
          next.set(pair, {
            pair,
            bid: p.bid,
            ask: p.ask,
            mid: p.mid,
            prevMid: prevEntry?.mid,
          });
        }
        return next;
      });
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPrices();
    const interval = setInterval(fetchPrices, 2000);
    return () => clearInterval(interval);
  }, [fetchPrices]);

  // Need a prices proxy route
  // Check if /api/prices exists, if not we use backend directly

  if (loading) {
    return (
      <div className="glass p-4">
        <div className="h-4 w-24 rounded mb-3" style={{ backgroundColor: "var(--color-bg-elevated)" }} />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          {[...Array(8)].map((_, i) => (
            <div
              key={i}
              className="h-16 rounded-lg animate-pulse"
              style={{ backgroundColor: "var(--color-bg-elevated)" }}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <motion.div
      className="glass p-4"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <h3 className="text-card-title mb-3" style={{ color: "var(--color-text-primary)" }}>
        Market Overview
      </h3>

      <motion.div
        className="grid grid-cols-2 lg:grid-cols-4 gap-2"
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        {PAIRS.map((pair) => {
          const data = prices.get(pair);
          if (!data) return null;

          const change = data.prevMid ? ((data.mid - data.prevMid) / data.prevMid) * 100 : 0;
          const direction = change > 0.0001 ? "up" : change < -0.0001 ? "down" : "flat";

          return (
            <motion.div
              key={pair}
              variants={itemVariants}
              className="rounded-lg px-3 py-2.5 cursor-default"
              style={{
                backgroundColor: "var(--color-bg-elevated)",
                border: "1px solid var(--color-border)",
              }}
              whileHover={{
                scale: 1.02,
                borderColor: "var(--color-accent)",
                transition: { duration: 0.15 },
              }}
              whileTap={{ scale: 0.98 }}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] font-bold" style={{ color: "var(--color-text-primary)" }}>
                  {formatPair(pair)}
                </span>
                {direction === "up" && <TrendingUp size={12} style={{ color: "var(--color-profit)" }} />}
                {direction === "down" && <TrendingDown size={12} style={{ color: "var(--color-loss)" }} />}
                {direction === "flat" && <Minus size={12} style={{ color: "var(--color-text-tertiary)" }} />}
              </div>
              <div className="font-mono text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
                {formatPrice(data.mid, pair)}
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className="text-[9px] font-mono" style={{ color: "var(--color-text-tertiary)" }}>
                  Spd: {formatSpread(data.bid, data.ask, pair)}
                </span>
                {change !== 0 && (
                  <span
                    className="text-[9px] font-mono font-bold"
                    style={{ color: change > 0 ? "var(--color-profit)" : "var(--color-loss)" }}
                  >
                    {change > 0 ? "+" : ""}{change.toFixed(3)}%
                  </span>
                )}
              </div>
            </motion.div>
          );
        })}
      </motion.div>
    </motion.div>
  );
}
