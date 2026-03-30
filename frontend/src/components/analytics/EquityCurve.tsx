"use client";

import { useMemo } from "react";
import { motion } from "motion/react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { TrendingUp, TrendingDown } from "lucide-react";
import EmptyState from "@/components/ui/EmptyState";

interface EquityCurveProps {
  data: { date: string; equity: number }[];
}

function formatUsd(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return dateStr;
  }
}

export default function EquityCurve({ data }: EquityCurveProps) {
  // Compute drawdown series + stats
  const { chartData, startingBalance, currentEquity, totalReturn, maxDrawdown, highWaterMark } =
    useMemo(() => {
      if (data.length === 0)
        return { chartData: [], startingBalance: 0, currentEquity: 0, totalReturn: 0, maxDrawdown: 0, highWaterMark: 0 };

      let hwm = data[0].equity;
      let maxDd = 0;

      const enriched = data.map((point) => {
        if (point.equity > hwm) hwm = point.equity;
        const drawdown = ((point.equity - hwm) / hwm) * 100;
        if (drawdown < maxDd) maxDd = drawdown;
        return {
          date: point.date,
          equity: point.equity,
          highWaterMark: hwm,
          drawdown: Math.abs(drawdown),
          drawdownPct: drawdown,
        };
      });

      const start = data[0].equity;
      const end = data[data.length - 1].equity;
      const ret = ((end - start) / start) * 100;

      return {
        chartData: enriched,
        startingBalance: start,
        currentEquity: end,
        totalReturn: ret,
        maxDrawdown: maxDd,
        highWaterMark: hwm,
      };
    }, [data]);

  const isPositive = totalReturn >= 0;

  return (
    <motion.div
      className="glass p-5"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h3 className="text-card-title" style={{ color: "var(--color-text-primary)" }}>
            Equity Curve
          </h3>
          {data.length > 0 && (
            <motion.div
              className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold"
              style={{
                backgroundColor: isPositive ? "var(--color-profit-dim)" : "var(--color-loss-dim)",
                color: isPositive ? "var(--color-profit)" : "var(--color-loss)",
              }}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.3, type: "spring", stiffness: 300 }}
            >
              {isPositive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {isPositive ? "+" : ""}{totalReturn.toFixed(2)}%
            </motion.div>
          )}
        </div>

        {data.length > 0 && (
          <div className="flex items-center gap-4 text-[11px]">
            <div>
              <span style={{ color: "var(--color-text-tertiary)" }}>Start: </span>
              <span className="font-mono" style={{ color: "var(--color-text-secondary)" }}>
                {formatUsd(startingBalance)}
              </span>
            </div>
            <div>
              <span style={{ color: "var(--color-text-tertiary)" }}>Now: </span>
              <span className="font-mono font-bold" style={{ color: "var(--color-text-primary)" }}>
                {formatUsd(currentEquity)}
              </span>
            </div>
            <div>
              <span style={{ color: "var(--color-text-tertiary)" }}>Max DD: </span>
              <span className="font-mono" style={{ color: "var(--color-loss)" }}>
                {maxDrawdown.toFixed(2)}%
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Chart */}
      {data.length === 0 ? (
        <EmptyState message="Equity curve is empty." description="Your account growth will be plotted here as Lumitrade closes trades." />
      ) : (
        <motion.div
          style={{ width: "100%", height: 320 }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.6 }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={chartData}
              margin={{ top: 10, right: 20, bottom: 5, left: 10 }}
            >
              <defs>
                {/* Equity gradient */}
                <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-brand)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--color-brand)" stopOpacity={0.02} />
                </linearGradient>
                {/* Drawdown gradient */}
                <linearGradient id="drawdownGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-loss)" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="var(--color-loss)" stopOpacity={0.02} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke="var(--color-border)"
                strokeOpacity={0.3}
              />

              <XAxis
                dataKey="date"
                tick={{ fill: "var(--color-text-tertiary)", fontSize: 10 }}
                stroke="var(--color-border)"
                strokeOpacity={0.3}
                tickLine={false}
                tickFormatter={formatDate}
              />
              <YAxis
                yAxisId="equity"
                tick={{ fill: "var(--color-text-tertiary)", fontSize: 10 }}
                stroke="var(--color-border)"
                strokeOpacity={0.3}
                tickLine={false}
                tickFormatter={(v: number) => formatUsd(v)}
              />
              <YAxis
                yAxisId="drawdown"
                orientation="right"
                tick={{ fill: "var(--color-text-tertiary)", fontSize: 10 }}
                stroke="var(--color-border)"
                strokeOpacity={0.3}
                tickLine={false}
                tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                reversed
              />

              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--color-bg-surface-solid)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--card-radius)",
                  fontSize: "12px",
                }}
                labelStyle={{ color: "var(--color-text-secondary)", marginBottom: 4 }}
                labelFormatter={(label) => formatDate(String(label))}
                formatter={(value, name) => {
                  const v = Number(value);
                  if (name === "equity") return [formatUsd(v), "Equity"];
                  if (name === "highWaterMark") return [formatUsd(v), "High Water Mark"];
                  if (name === "drawdown") return [`${v.toFixed(2)}%`, "Drawdown"];
                  return [String(value), String(name)];
                }}
              />

              {/* Starting balance reference line */}
              <ReferenceLine
                yAxisId="equity"
                y={startingBalance}
                stroke="var(--color-text-tertiary)"
                strokeDasharray="6 4"
                strokeOpacity={0.4}
              />

              {/* Drawdown area (right axis) */}
              <Area
                yAxisId="drawdown"
                type="monotone"
                dataKey="drawdown"
                fill="url(#drawdownGradient)"
                stroke="var(--color-loss)"
                strokeWidth={1}
                strokeOpacity={0.4}
                dot={false}
                animationDuration={1200}
                animationBegin={400}
              />

              {/* Equity area with gradient fill */}
              <Area
                yAxisId="equity"
                type="monotone"
                dataKey="equity"
                fill="url(#equityGradient)"
                stroke="var(--color-brand)"
                strokeWidth={2}
                dot={false}
                activeDot={{
                  r: 5,
                  fill: "var(--color-brand)",
                  stroke: "var(--color-bg-primary)",
                  strokeWidth: 2,
                }}
                animationDuration={1000}
                animationBegin={200}
              />

              {/* High water mark dashed line */}
              <Line
                yAxisId="equity"
                type="monotone"
                dataKey="highWaterMark"
                stroke="var(--color-text-tertiary)"
                strokeWidth={1}
                strokeDasharray="4 4"
                strokeOpacity={0.5}
                dot={false}
                animationDuration={1000}
                animationBegin={200}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </motion.div>
      )}

      {/* Legend */}
      {data.length > 0 && (
        <motion.div
          className="flex items-center justify-center gap-6 mt-3 text-[10px]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
        >
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 rounded" style={{ backgroundColor: "var(--color-brand)" }} />
            <span style={{ color: "var(--color-text-tertiary)" }}>Equity</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 rounded" style={{ backgroundColor: "var(--color-text-tertiary)", opacity: 0.5 }} />
            <span style={{ color: "var(--color-text-tertiary)" }}>High Water Mark</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-2 rounded-sm" style={{ backgroundColor: "var(--color-loss)", opacity: 0.3 }} />
            <span style={{ color: "var(--color-text-tertiary)" }}>Drawdown</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 rounded" style={{ backgroundColor: "var(--color-text-tertiary)", opacity: 0.4, borderTop: "1px dashed var(--color-text-tertiary)" }} />
            <span style={{ color: "var(--color-text-tertiary)" }}>Starting Balance</span>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
