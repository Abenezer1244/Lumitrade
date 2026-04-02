"use client";

import { Store, Users, TrendingUp, Star } from "lucide-react";

interface Strategy {
  name: string;
  author: string;
  winRate: number;
  profitFactor: number;
  subscribers: number;
  price: number;
  curvePoints: string;
}

const STRATEGIES: Strategy[] = [
  {
    name: "Trend Rider",
    author: "Alex K.",
    winRate: 67,
    profitFactor: 1.8,
    subscribers: 142,
    price: 49,
    curvePoints: "M0,40 C20,38 40,30 60,32 C80,34 100,20 120,18 C140,15 160,22 180,10 L180,60 L0,60 Z",
  },
  {
    name: "Asian Session Scalper",
    author: "Sarah M.",
    winRate: 72,
    profitFactor: 2.1,
    subscribers: 89,
    price: 79,
    curvePoints: "M0,45 C20,42 40,35 60,28 C80,30 100,22 120,15 C140,18 160,10 180,8 L180,60 L0,60 Z",
  },
  {
    name: "JPY Momentum",
    author: "David L.",
    winRate: 61,
    profitFactor: 1.5,
    subscribers: 203,
    price: 39,
    curvePoints: "M0,35 C20,40 40,32 60,35 C80,28 100,30 120,22 120,25 C140,20 160,18 180,15 L180,60 L0,60 Z",
  },
];

function MiniEquityCurve({ points }: { points: string }) {
  return (
    <svg viewBox="0 0 180 60" className="w-full h-16" preserveAspectRatio="none">
      <defs>
        <linearGradient id="curve-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-profit)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="var(--color-profit)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={points} fill="url(#curve-fill)" />
      <path
        d={points.split("L")[0]}
        fill="none"
        stroke="var(--color-profit)"
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export default function MarketplacePage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: "var(--color-accent)", opacity: 0.15 }}
        >
          <Store size={20} style={{ color: "var(--color-accent)" }} />
        </div>
        <div>
          <h1
            className="text-xl font-bold"
            style={{ color: "var(--color-text-primary)", fontFamily: "'Space Grotesk', sans-serif" }}
          >
            Strategy Marketplace
          </h1>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Browse and subscribe to community-built trading strategies
          </p>
        </div>
      </div>

      {/* Strategy Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {STRATEGIES.map((s) => (
          <div key={s.name} className="glass p-5 flex flex-col">
            {/* Author row */}
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3
                  className="text-base font-bold"
                  style={{ color: "var(--color-text-primary)", fontFamily: "'Space Grotesk', sans-serif" }}
                >
                  {s.name}
                </h3>
                <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
                  by {s.author}
                </p>
              </div>
              <div className="flex items-center gap-1">
                <Star size={12} style={{ color: "var(--color-warning)", fill: "var(--color-warning)" }} />
                <Star size={12} style={{ color: "var(--color-warning)", fill: "var(--color-warning)" }} />
                <Star size={12} style={{ color: "var(--color-warning)", fill: "var(--color-warning)" }} />
                <Star size={12} style={{ color: "var(--color-warning)", fill: "var(--color-warning)" }} />
                <Star size={12} style={{ color: "var(--color-text-tertiary)" }} />
              </div>
            </div>

            {/* Mini curve */}
            <div
              className="rounded-lg overflow-hidden mb-4"
              style={{ backgroundColor: "var(--color-bg-primary)" }}
            >
              <MiniEquityCurve points={s.curvePoints} />
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div>
                <p className="text-[10px] uppercase tracking-wider" style={{ color: "var(--color-text-tertiary)" }}>
                  Win Rate
                </p>
                <p className="font-mono text-sm font-bold" style={{ color: "var(--color-profit)" }}>
                  {s.winRate}%
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider" style={{ color: "var(--color-text-tertiary)" }}>
                  Profit Factor
                </p>
                <p className="font-mono text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
                  {s.profitFactor.toFixed(1)}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider" style={{ color: "var(--color-text-tertiary)" }}>
                  Subscribers
                </p>
                <p className="font-mono text-sm font-bold flex items-center gap-1" style={{ color: "var(--color-text-primary)" }}>
                  <Users size={11} style={{ color: "var(--color-text-secondary)" }} />
                  {s.subscribers}
                </p>
              </div>
            </div>

            {/* Price + Subscribe */}
            <div className="flex items-center justify-between mt-auto pt-3" style={{ borderTop: "1px solid var(--color-border)" }}>
              <span className="font-mono text-lg font-bold" style={{ color: "var(--color-text-primary)" }}>
                ${s.price}<span className="text-xs font-normal" style={{ color: "var(--color-text-tertiary)" }}>/mo</span>
              </span>
              <button
                disabled
                className="text-xs font-medium px-4 py-2 rounded-lg opacity-50 cursor-not-allowed"
                style={{ backgroundColor: "var(--color-accent)", color: "#fff" }}
              >
                Subscribe
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Bottom Banner */}
      <div
        className="glass p-5 text-center"
        style={{ borderLeft: "3px solid var(--color-warning)" }}
      >
        <div className="flex items-center justify-center gap-2 mb-2">
          <TrendingUp size={16} style={{ color: "var(--color-warning)" }} />
          <span
            className="text-xs font-bold uppercase tracking-wider"
            style={{ color: "var(--color-warning)" }}
          >
            Phase 3
          </span>
        </div>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Marketplace launching in Phase 3 — Publish your own strategy after 90+ live trading days
        </p>
      </div>
    </div>
  );
}
