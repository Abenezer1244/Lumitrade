"use client";

import { FlaskConical, Play, Calendar, TrendingUp, BarChart3 } from "lucide-react";

const PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "EUR/GBP", "XAU/USD", "USD/CAD", "GBP/JPY"];

function MockEquityCurve() {
  return (
    <svg viewBox="0 0 400 160" className="w-full h-40" preserveAspectRatio="none">
      <defs>
        <linearGradient id="bt-curve-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-profit)" stopOpacity="0.2" />
          <stop offset="100%" stopColor="var(--color-profit)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Grid lines */}
      {[40, 80, 120].map((y) => (
        <line
          key={y}
          x1="0"
          y1={y}
          x2="400"
          y2={y}
          stroke="var(--color-border)"
          strokeWidth="0.5"
          strokeDasharray="4 4"
        />
      ))}
      {/* Area fill */}
      <path
        d="M0,140 C30,135 60,130 90,125 C120,128 150,115 180,105 C210,110 240,95 270,80 C300,85 330,65 360,55 C380,50 400,40 400,40 L400,160 L0,160 Z"
        fill="url(#bt-curve-fill)"
      />
      {/* Line */}
      <path
        d="M0,140 C30,135 60,130 90,125 C120,128 150,115 180,105 C210,110 240,95 270,80 C300,85 330,65 360,55 C380,50 400,40 400,40"
        fill="none"
        stroke="var(--color-profit)"
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
      {/* Drawdown region */}
      <path
        d="M120,128 C135,132 150,130 165,128"
        fill="none"
        stroke="var(--color-loss)"
        strokeWidth="1.5"
        strokeDasharray="3 3"
        vectorEffect="non-scaling-stroke"
        opacity="0.6"
      />
    </svg>
  );
}

interface StatCardProps {
  label: string;
  value: string;
  color?: string;
}

function StatCard({ label, value, color }: StatCardProps) {
  return (
    <div
      className="rounded-lg p-3"
      style={{
        backgroundColor: "var(--color-bg-primary)",
        border: "1px solid var(--color-border)",
      }}
    >
      <p className="text-[10px] uppercase tracking-wider mb-1" style={{ color: "var(--color-text-tertiary)" }}>
        {label}
      </p>
      <p className="font-mono text-base font-bold" style={{ color: color ?? "var(--color-text-primary)" }}>
        {value}
      </p>
    </div>
  );
}

export default function BacktestPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: "var(--color-accent)", opacity: 0.15 }}
        >
          <FlaskConical size={20} style={{ color: "var(--color-accent)" }} />
        </div>
        <div>
          <h1
            className="text-xl font-bold"
            style={{ color: "var(--color-text-primary)", fontFamily: "'Space Grotesk', sans-serif" }}
          >
            Backtesting Studio
          </h1>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Replay historical data through Lumitrade&apos;s AI engine
          </p>
        </div>
      </div>

      {/* Setup Panel */}
      <div className="glass p-5">
        <h2
          className="text-sm font-bold uppercase tracking-wider mb-4"
          style={{ color: "var(--color-text-primary)", fontFamily: "'DM Sans', sans-serif" }}
        >
          Configuration
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Date Range */}
          <div>
            <label
              className="text-xs uppercase tracking-wider mb-2 block"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              Date Range
            </label>
            <div className="flex items-center gap-2">
              <div
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm w-full cursor-not-allowed opacity-70"
                style={{
                  backgroundColor: "var(--color-bg-primary)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-secondary)",
                }}
              >
                <Calendar size={14} />
                <span className="font-mono">Jan 2024 — Dec 2025</span>
              </div>
            </div>
          </div>

          {/* Pair Selector */}
          <div>
            <label
              className="text-xs uppercase tracking-wider mb-2 block"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              Pairs
            </label>
            <div className="flex flex-wrap gap-1.5">
              {PAIRS.slice(0, 4).map((pair, i) => (
                <span
                  key={pair}
                  className="text-[10px] font-mono px-2 py-1 rounded cursor-not-allowed"
                  style={{
                    backgroundColor: i < 2 ? "var(--color-accent)" : "var(--color-bg-primary)",
                    color: i < 2 ? "#fff" : "var(--color-text-secondary)",
                    border: `1px solid ${i < 2 ? "var(--color-accent)" : "var(--color-border)"}`,
                    opacity: 0.7,
                  }}
                >
                  {pair}
                </span>
              ))}
              <span
                className="text-[10px] font-mono px-2 py-1 rounded"
                style={{ color: "var(--color-text-tertiary)" }}
              >
                +{PAIRS.length - 4} more
              </span>
            </div>
          </div>

          {/* Confidence Threshold */}
          <div>
            <label
              className="text-xs uppercase tracking-wider mb-2 block"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              Min Confidence
            </label>
            <div className="space-y-2">
              <div
                className="relative h-2 rounded-full cursor-not-allowed"
                style={{ backgroundColor: "var(--color-bg-primary)" }}
              >
                <div
                  className="absolute left-0 top-0 h-full rounded-full"
                  style={{ width: "65%", backgroundColor: "var(--color-accent)", opacity: 0.7 }}
                />
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full"
                  style={{
                    left: "calc(65% - 8px)",
                    backgroundColor: "var(--color-accent)",
                    border: "2px solid var(--color-bg-surface)",
                    opacity: 0.7,
                  }}
                />
              </div>
              <p className="font-mono text-sm text-right" style={{ color: "var(--color-text-secondary)" }}>
                0.65
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Results Area */}
      <div className="glass p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BarChart3 size={16} style={{ color: "var(--color-profit)" }} />
            <h2
              className="text-sm font-bold uppercase tracking-wider"
              style={{ color: "var(--color-text-primary)", fontFamily: "'DM Sans', sans-serif" }}
            >
              Backtest Results
            </h2>
          </div>
          <span
            className="text-[10px] font-mono px-2 py-0.5 rounded"
            style={{ backgroundColor: "var(--color-bg-elevated)", color: "var(--color-text-tertiary)" }}
          >
            SAMPLE DATA
          </span>
        </div>

        {/* Equity Curve */}
        <div
          className="rounded-lg overflow-hidden mb-4"
          style={{
            backgroundColor: "var(--color-bg-primary)",
            border: "1px solid var(--color-border)",
          }}
        >
          <MockEquityCurve />
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Total Trades" value="156" />
          <StatCard label="Win Rate" value="58%" color="var(--color-profit)" />
          <StatCard label="Profit Factor" value="1.7" color="var(--color-profit)" />
          <StatCard label="Max Drawdown" value="-8.2%" color="var(--color-loss)" />
        </div>
      </div>

      {/* Run Button */}
      <div className="flex justify-center">
        <button
          disabled
          className="flex items-center gap-2 text-sm font-medium px-6 py-3 rounded-lg opacity-50 cursor-not-allowed"
          style={{ backgroundColor: "var(--color-accent)", color: "#fff" }}
        >
          <Play size={16} />
          Run Backtest
        </button>
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
          Coming in Phase 3 — Replay 24 months of market data through Lumitrade&apos;s AI
        </p>
      </div>
    </div>
  );
}
