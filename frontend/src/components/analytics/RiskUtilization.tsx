"use client";

import { motion } from "motion/react";
import { Shield, AlertTriangle } from "lucide-react";
import { useAccount } from "@/hooks/useAccount";
import { useSystemStatus } from "@/hooks/useSystemStatus";

interface GaugeProps {
  label: string;
  current: number;
  max: number;
  unit: string;
  warningAt?: number; // percentage at which to show warning color
}

function Gauge({ label, current, max, unit, warningAt = 70 }: GaugeProps) {
  const pct = max > 0 ? Math.min((current / max) * 100, 100) : 0;
  const color =
    pct >= 90 ? "var(--color-loss)" :
    pct >= warningAt ? "var(--color-warning)" :
    "var(--color-profit)";

  return (
    <div className="py-2.5">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[11px]" style={{ color: "var(--color-text-secondary)" }}>{label}</span>
        <span className="text-[11px] font-mono font-bold" style={{ color }}>
          {typeof current === "number" && current % 1 !== 0 ? current.toFixed(2) : current}{unit} / {max}{unit}
        </span>
      </div>
      <div
        className="h-2 rounded-full overflow-hidden"
        style={{ backgroundColor: "var(--color-bg-elevated)" }}
      >
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

export default function RiskUtilization() {
  const { account } = useAccount();
  const { health } = useSystemStatus();

  const balance = parseFloat(account?.balance || "0");
  const marginUsed = parseFloat(account?.margin_used || "0");
  const marginAvailable = parseFloat(account?.margin_available || "0");
  const openCount = account?.open_trade_count || 0;
  const mode = account?.mode || "PAPER";

  const riskState = health?.trading?.mode === "PAPER" ? "NORMAL" :
    (health?.components as Record<string, { state?: string }>)?.risk_engine?.state || "NORMAL";

  // Calculate utilization metrics
  const marginPct = balance > 0 ? (marginUsed / balance) * 100 : 0;
  const dailyPnl = parseFloat(account?.daily_pnl_usd || "0");
  const dailyPnlPct = balance > 0 ? (dailyPnl / balance) * 100 : 0;

  const stateColor =
    riskState === "NORMAL" ? "var(--color-profit)" :
    riskState === "CAUTIOUS" ? "var(--color-warning)" :
    "var(--color-loss)";

  return (
    <motion.div
      className="glass p-5"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-6 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: "var(--color-accent-glow)" }}
          >
            <Shield size={12} style={{ color: "var(--color-accent)" }} />
          </div>
          <h3 className="text-card-title" style={{ color: "var(--color-text-primary)" }}>
            Risk
          </h3>
        </div>
        <motion.div
          className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold"
          style={{
            backgroundColor: `${stateColor}15`,
            color: stateColor,
          }}
          animate={{ opacity: riskState !== "NORMAL" ? [1, 0.6, 1] : 1 }}
          transition={riskState !== "NORMAL" ? { duration: 1.5, repeat: Infinity } : {}}
        >
          {riskState !== "NORMAL" && <AlertTriangle size={10} />}
          {riskState}
        </motion.div>
      </div>

      {/* Gauges */}
      <div className="space-y-1">
        <Gauge
          label="Open Positions"
          current={openCount}
          max={100}
          unit=""
          warningAt={80}
        />
        <Gauge
          label="Margin Used"
          current={marginPct}
          max={100}
          unit="%"
          warningAt={60}
        />
        <Gauge
          label="Daily P&L"
          current={Math.abs(dailyPnlPct)}
          max={5}
          unit="%"
          warningAt={60}
        />
      </div>

      {/* Summary stats */}
      <div
        className="grid grid-cols-3 gap-3 mt-4 pt-3"
        style={{ borderTop: "1px solid var(--color-border)" }}
      >
        <div className="text-center">
          <p className="text-[9px] uppercase tracking-wider" style={{ color: "var(--color-text-tertiary)" }}>
            Margin Used
          </p>
          <p className="font-mono text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
            ${marginUsed.toLocaleString("en-US", { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="text-center">
          <p className="text-[9px] uppercase tracking-wider" style={{ color: "var(--color-text-tertiary)" }}>
            Available
          </p>
          <p className="font-mono text-sm font-bold" style={{ color: "var(--color-profit)" }}>
            ${marginAvailable.toLocaleString("en-US", { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="text-center">
          <p className="text-[9px] uppercase tracking-wider" style={{ color: "var(--color-text-tertiary)" }}>
            Mode
          </p>
          <p
            className="font-mono text-sm font-bold"
            style={{ color: mode === "LIVE" ? "var(--color-profit)" : "var(--color-warning)" }}
          >
            {mode}
          </p>
        </div>
      </div>
    </motion.div>
  );
}
