"use client";

import { FlaskConical } from "lucide-react";

export default function BacktestPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 text-center px-4">
      <div
        className="w-16 h-16 rounded-2xl flex items-center justify-center"
        style={{ backgroundColor: "#3D8EFF1A" }}
      >
        <FlaskConical size={32} style={{ color: "#3D8EFF" }} />
      </div>

      <div className="space-y-2">
        <h1
          className="text-2xl font-bold"
          style={{ color: "#E2E8F0", fontFamily: "'Space Grotesk', sans-serif" }}
        >
          Strategy Backtesting
        </h1>
        <p
          className="text-base font-semibold tracking-wide"
          style={{ color: "#3D8EFF" }}
        >
          Coming Soon
        </p>
      </div>

      <p
        className="max-w-md text-sm leading-relaxed"
        style={{ color: "#8899AA" }}
      >
        Backtest your trading strategies against historical data. This feature is under development.
      </p>

      <div
        className="rounded-xl px-6 py-4 max-w-md w-full"
        style={{
          backgroundColor: "#111D2E",
          border: "1px solid #1E3048",
        }}
      >
        <p className="text-xs uppercase tracking-widest font-semibold" style={{ color: "#8899AA" }}>
          What to expect
        </p>
        <ul className="mt-3 space-y-2 text-sm text-left" style={{ color: "#8899AA" }}>
          <li>Replay 24+ months of historical market data</li>
          <li>Measure win rate, profit factor, and max drawdown</li>
          <li>Compare strategies before deploying capital</li>
        </ul>
      </div>
    </div>
  );
}
