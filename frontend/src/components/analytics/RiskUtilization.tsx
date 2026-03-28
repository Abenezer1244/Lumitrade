"use client";

import { motion } from "motion/react";
import { Shield, AlertTriangle } from "lucide-react";
import { useAccount } from "@/hooks/useAccount";
import { useSystemStatus } from "@/hooks/useSystemStatus";

/* ── Gauge with gradient fill ──────────────────────────────── */

function Gauge({ label, current, max, unit, warningAt = 70 }: {
  label: string;
  current: number;
  max: number;
  unit: string;
  warningAt?: number;
}) {
  const pct = max > 0 ? Math.min((current / max) * 100, 100) : 0;
  const color =
    pct >= 90 ? "var(--color-loss)" :
    pct >= warningAt ? "var(--color-warning)" :
    "var(--color-profit)";

  return (
    <div className="py-2">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[11px]" style={{ color: "var(--color-text-secondary)" }}>{label}</span>
        <span className="text-[11px] font-mono font-bold tabular-nums" style={{ color }}>
          {typeof current === "number" && current % 1 !== 0 ? current.toFixed(2) : current}{unit} / {max}{unit}
        </span>
      </div>
      <div
        className="h-1.5 rounded-full overflow-hidden"
        style={{ backgroundColor: "rgba(18, 30, 52, 0.6)" }}
      >
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
    </div>
  );
}

/* ── Main Component ────────────────────────────────────────── */

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

  const marginPct = balance > 0 ? (marginUsed / balance) * 100 : 0;
  const dailyPnl = parseFloat(account?.daily_pnl_usd || "0");
  const dailyPnlPct = balance > 0 ? (dailyPnl / balance) * 100 : 0;

  const stateColor =
    riskState === "NORMAL" ? "var(--color-profit)" :
    riskState === "CAUTIOUS" ? "var(--color-warning)" :
    "var(--color-loss)";

  return (
    <motion.div
      className="glass-muted p-5"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Shield size={14} style={{ color: "var(--color-accent)" }} />
          <h3 className="text-card-title" style={{ color: "var(--color-text-primary)" }}>
            Risk
          </h3>
        </div>
        <motion.span
          className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-widest"
          style={{ backgroundColor: `${stateColor}12`, color: stateColor }}
          animate={{ opacity: riskState !== "NORMAL" ? [1, 0.6, 1] : 1 }}
          transition={riskState !== "NORMAL" ? { duration: 1.5, repeat: Infinity } : {}}
        >
          {riskState !== "NORMAL" && <AlertTriangle size={9} />}
          {riskState}
        </motion.span>
      </div>

      {/* Gauges */}
      <div className="space-y-0.5">
        <Gauge label="Open Positions" current={openCount} max={100} unit="" warningAt={80} />
        <Gauge label="Margin Used" current={marginPct} max={100} unit="%" warningAt={60} />
        <Gauge label="Daily P&L" current={Math.abs(dailyPnlPct)} max={5} unit="%" warningAt={60} />
      </div>

      {/* Summary — compact grid */}
      <div
        className="grid grid-cols-3 gap-2 mt-3 pt-3"
        style={{ borderTop: "1px solid rgba(30, 55, 92, 0.2)" }}
      >
        <div className="text-center">
          <p className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: "var(--color-text-tertiary)" }}>
            Margin
          </p>
          <p className="font-mono text-[13px] font-bold" style={{ color: "var(--color-text-primary)" }}>
            ${marginUsed.toLocaleString("en-US", { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="text-center">
          <p className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: "var(--color-text-tertiary)" }}>
            Available
          </p>
          <p className="font-mono text-[13px] font-bold" style={{ color: "var(--color-profit)" }}>
            ${marginAvailable.toLocaleString("en-US", { maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="text-center">
          <p className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: "var(--color-text-tertiary)" }}>
            Mode
          </p>
          <p
            className="font-mono text-[13px] font-bold"
            style={{ color: mode === "LIVE" ? "var(--color-profit)" : "var(--color-warning)" }}
          >
            {mode}
          </p>
        </div>
      </div>
    </motion.div>
  );
}
