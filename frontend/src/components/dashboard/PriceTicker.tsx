"use client";

import { useEffect, useState, useRef } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { formatPair, formatPrice } from "@/lib/formatters";

interface PriceData {
  pair: string;
  bid: number;
  ask: number;
  spread: number;
}

const PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD", "USD_CAD", "NZD_USD", "XAU_USD"];

function formatSpread(pair: string, spread: number): string {
  const pipMultiplier = pair.includes("JPY") ? 100 : pair === "XAU_USD" ? 100 : 10000;
  return (spread * pipMultiplier).toFixed(1);
}

export default function PriceTicker() {
  const [prices, setPrices] = useState<PriceData[]>([]);
  const [prevPrices, setPrevPrices] = useState<Record<string, number>>({});
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function fetchPrices() {
      try {
        const res = await fetch("/api/prices");
        if (!res.ok) return;
        const data = await res.json();
        if (Array.isArray(data)) {
          setPrevPrices((prev) => {
            const next: Record<string, number> = {};
            prices.forEach((p) => { next[p.pair] = p.bid; });
            return { ...prev, ...next };
          });
          setPrices(data);
        }
      } catch { /* silent */ }
    }
    fetchPrices();
    const interval = setInterval(fetchPrices, 3000);
    return () => clearInterval(interval);
  }, [prices]);

  if (prices.length === 0) return null;

  // Double the array for seamless marquee
  const tickerItems = [...prices, ...prices];

  return (
    <div
      className="overflow-hidden relative"
      style={{
        borderBottom: "1px solid var(--color-border)",
        background: "var(--color-bg-elevated)",
      }}
    >
      <div
        ref={scrollRef}
        className="flex items-center gap-6 py-1.5 px-4 animate-ticker whitespace-nowrap"
      >
        {tickerItems.map((p, i) => {
          const prev = prevPrices[p.pair] ?? p.bid;
          const direction = p.bid > prev ? "up" : p.bid < prev ? "down" : "flat";
          const TrendIcon = direction === "up" ? TrendingUp : direction === "down" ? TrendingDown : Minus;
          const trendColor = direction === "up" ? "var(--color-profit)" : direction === "down" ? "var(--color-loss)" : "var(--color-text-tertiary)";

          return (
            <div key={`${p.pair}-${i}`} className="flex items-center gap-2 shrink-0">
              <span className="text-[11px] font-bold" style={{ color: "var(--color-text-primary)" }}>
                {formatPair(p.pair)}
              </span>
              <span className="text-[11px] font-mono" style={{ color: trendColor }}>
                {formatPrice(p.bid, p.pair)}
              </span>
              <TrendIcon size={10} style={{ color: trendColor }} />
              <span className="text-[9px] font-mono" style={{ color: "var(--color-text-tertiary)" }}>
                {formatSpread(p.pair, p.spread)}p
              </span>
              {i < tickerItems.length - 1 && (
                <span className="text-[8px] mx-1" style={{ color: "var(--color-border)" }}>|</span>
              )}
            </div>
          );
        })}
      </div>
      <style jsx>{`
        @keyframes ticker-scroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .animate-ticker {
          animation: ticker-scroll 30s linear infinite;
        }
        .animate-ticker:hover {
          animation-play-state: paused;
        }
      `}</style>
    </div>
  );
}
