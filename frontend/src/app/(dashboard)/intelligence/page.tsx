"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  TrendingUp,
  Clock,
  Shield,
  Lightbulb,
  ChevronDown,
  ChevronUp,
  BarChart3,
  AlertTriangle,
  FileBarChart,
} from "lucide-react";
import { formatSignedUsd } from "@/lib/formatters";

/* ── Types (mirror the API response) ──────────────────────── */

import type {
  PairStat,
  SessionStat,
  WeeklyReport,
} from "@/types/intelligence";

/* ── Helpers ───────────────────────────────────────────────── */

function formatWeekRange(start: string, end: string): string {
  const s = new Date(start + "T00:00:00Z");
  const e = new Date(end + "T00:00:00Z");
  const fmt = (d: Date) =>
    d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    });
  const year = s.getUTCFullYear();
  return `${fmt(s)} - ${fmt(e)}, ${year}`;
}

function pnlColor(value: number): string {
  if (value > 0) return "var(--color-profit)";
  if (value < 0) return "var(--color-loss)";
  return "var(--color-text-secondary)";
}

function pnlClass(value: number): string {
  if (value > 0) return "text-profit";
  if (value < 0) return "text-loss";
  return "text-secondary";
}

function formatUsd(value: number): string {
  return formatSignedUsd(value);
}

/* ── Session Heatmap ──────────────────────────────────────── */

interface SessionHeatmapProps {
  stats: SessionStat[];
}

function SessionHeatmap({ stats }: SessionHeatmapProps) {
  const activeStats = stats.filter((s) => s.trades > 0);
  if (activeStats.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--color-text-tertiary)" }}>
        No session data available.
      </p>
    );
  }

  const maxAbsPnl = Math.max(...stats.map((s) => Math.abs(s.pnlUsd)), 0.01);

  return (
    <div className="grid grid-cols-12 gap-1">
      {stats.map((s) => {
        const intensity = s.trades > 0 ? Math.abs(s.pnlUsd) / maxAbsPnl : 0;
        const alpha = Math.max(0.1, intensity);
        let bg: string;
        if (s.trades === 0) {
          bg = "rgba(74, 94, 128, 0.1)";
        } else if (s.pnlUsd > 0) {
          bg = `rgba(0, 200, 150, ${alpha * 0.7})`;
        } else if (s.pnlUsd < 0) {
          bg = `rgba(255, 77, 106, ${alpha * 0.7})`;
        } else {
          bg = "rgba(138, 155, 192, 0.2)";
        }

        return (
          <div
            key={s.hour}
            className="relative group rounded"
            style={{
              backgroundColor: bg,
              aspectRatio: "1",
              minHeight: "24px",
            }}
            title={`${s.hour.toString().padStart(2, "0")}:00 UTC | ${s.trades} trades | ${formatUsd(s.pnlUsd)}`}
          >
            <span
              className="absolute inset-0 flex items-center justify-center font-mono text-[9px]"
              style={{ color: "var(--color-text-secondary)" }}
            >
              {s.hour.toString().padStart(2, "0")}
            </span>
            {/* Tooltip */}
            <div
              className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 rounded text-xs font-mono whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10"
              style={{
                backgroundColor: "var(--color-bg-elevated)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text-primary)",
              }}
            >
              {s.trades > 0
                ? `${s.trades} trades, ${formatUsd(s.pnlUsd)}`
                : "No trades"}
            </div>
          </div>
        );
      })}
      {/* Legend row */}
      <div
        className="col-span-12 flex items-center gap-3 mt-1 text-[10px] font-label uppercase tracking-wide"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        <span className="flex items-center gap-1">
          <span
            className="inline-block w-2.5 h-2.5 rounded-sm"
            style={{ backgroundColor: "rgba(0, 200, 150, 0.5)" }}
          />
          Profit
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block w-2.5 h-2.5 rounded-sm"
            style={{ backgroundColor: "rgba(255, 77, 106, 0.5)" }}
          />
          Loss
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block w-2.5 h-2.5 rounded-sm"
            style={{ backgroundColor: "rgba(74, 94, 128, 0.1)" }}
          />
          No trades
        </span>
      </div>
    </div>
  );
}

/* ── Pair Performance Table ───────────────────────────────── */

interface PairTableProps {
  pairs: PairStat[];
}

function PairTable({ pairs }: PairTableProps) {
  if (pairs.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--color-text-tertiary)" }}>
        No pair data available.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr
            className="text-[10px] font-label uppercase tracking-wide"
            style={{
              color: "var(--color-text-tertiary)",
              borderBottom: "1px solid var(--color-border)",
            }}
          >
            <th className="text-left py-2 pr-3">Pair</th>
            <th className="text-right py-2 px-3">Trades</th>
            <th className="text-right py-2 px-3">WR%</th>
            <th className="text-right py-2 pl-3">P&L</th>
          </tr>
        </thead>
        <tbody>
          {pairs.map((p) => (
            <tr
              key={p.pair}
              style={{ borderBottom: "1px solid rgba(30, 58, 95, 0.4)" }}
            >
              <td
                className="py-1.5 pr-3 font-mono text-sm"
                style={{ color: "var(--color-text-primary)" }}
              >
                {p.pair.replace("_", "/")}
              </td>
              <td
                className="py-1.5 px-3 font-mono text-right"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {p.trades}
              </td>
              <td
                className="py-1.5 px-3 font-mono text-right"
                style={{ color: p.winRate >= 50 ? "var(--color-profit)" : "var(--color-loss)" }}
              >
                {p.winRate}%
              </td>
              <td
                className={`py-1.5 pl-3 font-mono text-right ${pnlClass(p.pnlUsd)}`}
              >
                {formatUsd(p.pnlUsd)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Report Card ──────────────────────────────────────────── */

interface ReportCardProps {
  report: WeeklyReport;
  index: number;
}

function ReportCard({ report, index }: ReportCardProps) {
  const [expanded, setExpanded] = useState(index === 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4 }}
      className="glass p-5 rounded-lg"
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: "rgba(61, 142, 255, 0.12)" }}
          >
            <FileBarChart size={18} style={{ color: "var(--color-accent)" }} />
          </div>
          <div className="text-left">
            <h3
              className="font-display text-base font-semibold"
              style={{ color: "var(--color-text-primary)" }}
            >
              {formatWeekRange(report.weekStart, report.weekEnd)}
            </h3>
            <div
              className="flex items-center gap-3 mt-0.5 text-xs font-mono"
              style={{ color: "var(--color-text-secondary)" }}
            >
              <span>{report.totalTrades} trades</span>
              <span
                style={{
                  color:
                    report.winRate >= 50
                      ? "var(--color-profit)"
                      : "var(--color-loss)",
                }}
              >
                {report.winRate}% WR
              </span>
              <span className={pnlClass(report.totalPnlUsd)}>
                {formatUsd(report.totalPnlUsd)}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-mono px-2 py-0.5 rounded"
            style={{
              backgroundColor:
                report.totalPnlUsd >= 0
                  ? "rgba(0, 200, 150, 0.12)"
                  : "rgba(255, 77, 106, 0.12)",
              color: pnlColor(report.totalPnlUsd),
            }}
          >
            {report.wins}W / {report.losses}L
          </span>
          {expanded ? (
            <ChevronUp
              size={16}
              style={{ color: "var(--color-text-tertiary)" }}
            />
          ) : (
            <ChevronDown
              size={16}
              style={{ color: "var(--color-text-tertiary)" }}
            />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            <div
              className="mt-5 pt-5 grid grid-cols-1 lg:grid-cols-2 gap-5"
              style={{ borderTop: "1px solid var(--color-border)" }}
            >
              {/* Macro Summary */}
              <div
                className="rounded-lg p-4"
                style={{
                  backgroundColor: "var(--color-bg-elevated)",
                  border: "1px solid var(--color-border)",
                }}
              >
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp
                    size={15}
                    style={{ color: "var(--color-accent)" }}
                  />
                  <h4
                    className="text-xs font-label uppercase tracking-wide"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    Macro Summary
                  </h4>
                </div>
                <PairTable pairs={report.pairStats} />
              </div>

              {/* Session Performance */}
              <div
                className="rounded-lg p-4"
                style={{
                  backgroundColor: "var(--color-bg-elevated)",
                  border: "1px solid var(--color-border)",
                }}
              >
                <div className="flex items-center gap-2 mb-3">
                  <Clock
                    size={15}
                    style={{ color: "var(--color-accent)" }}
                  />
                  <h4
                    className="text-xs font-label uppercase tracking-wide"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    Session Performance
                  </h4>
                  <span
                    className="text-[10px] font-mono ml-auto"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    UTC hours
                  </span>
                </div>
                <SessionHeatmap stats={report.sessionStats} />
              </div>

              {/* Risk Assessment */}
              <div
                className="rounded-lg p-4"
                style={{
                  backgroundColor: "var(--color-bg-elevated)",
                  border: "1px solid var(--color-border)",
                }}
              >
                <div className="flex items-center gap-2 mb-3">
                  <Shield
                    size={15}
                    style={{ color: "var(--color-warning)" }}
                  />
                  <h4
                    className="text-xs font-label uppercase tracking-wide"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    Risk Assessment
                  </h4>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <RiskMetric
                    label="Max Drawdown"
                    value={`$${report.riskAssessment.maxDrawdownUsd.toFixed(2)}`}
                    warn={report.riskAssessment.maxDrawdownUsd > 100}
                  />
                  <RiskMetric
                    label="Consecutive Losses"
                    value={report.riskAssessment.maxConsecutiveLosses.toString()}
                    warn={report.riskAssessment.maxConsecutiveLosses >= 3}
                  />
                  <RiskMetric
                    label="Avg Loss"
                    value={`$${report.riskAssessment.averageLossUsd.toFixed(2)}`}
                    warn={false}
                  />
                  <RiskMetric
                    label="R:R Ratio"
                    value={`${report.riskAssessment.riskRewardRatio.toFixed(2)}:1`}
                    warn={report.riskAssessment.riskRewardRatio < 1.5 && report.riskAssessment.riskRewardRatio > 0}
                  />
                  <RiskMetric
                    label="Largest Win"
                    value={formatUsd(report.riskAssessment.largestWinUsd)}
                    positive
                    warn={false}
                  />
                  <RiskMetric
                    label="Largest Loss"
                    value={formatUsd(report.riskAssessment.largestLossUsd)}
                    warn={false}
                  />
                </div>
              </div>

              {/* Recommendations */}
              <div
                className="rounded-lg p-4"
                style={{
                  backgroundColor: "var(--color-bg-elevated)",
                  border: "1px solid var(--color-border)",
                }}
              >
                <div className="flex items-center gap-2 mb-3">
                  <Lightbulb
                    size={15}
                    style={{ color: "var(--color-profit)" }}
                  />
                  <h4
                    className="text-xs font-label uppercase tracking-wide"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    Recommendations
                  </h4>
                </div>
                <ul className="space-y-2.5">
                  {report.recommendations.map((rec, i) => (
                    <li key={i} className="flex gap-2 text-sm leading-relaxed">
                      <span
                        className="mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: "var(--color-accent)" }}
                      />
                      <span style={{ color: "var(--color-text-primary)" }}>
                        {rec}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/* ── Risk Metric Cell ─────────────────────────────────────── */

interface RiskMetricProps {
  label: string;
  value: string;
  warn: boolean;
  positive?: boolean;
}

function RiskMetric({ label, value, warn, positive }: RiskMetricProps) {
  let valueColor = "var(--color-text-primary)";
  if (warn) valueColor = "var(--color-warning)";
  if (positive) valueColor = "var(--color-profit)";

  return (
    <div>
      <p
        className="text-[10px] font-label uppercase tracking-wide mb-0.5"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        {label}
      </p>
      <div className="flex items-center gap-1">
        {warn && (
          <AlertTriangle
            size={11}
            style={{ color: "var(--color-warning)" }}
          />
        )}
        <span className="font-mono text-sm" style={{ color: valueColor }}>
          {value}
        </span>
      </div>
    </div>
  );
}

/* ── Empty State ──────────────────────────────────────────── */

function EmptyState() {
  return (
    <div className="glass p-12 rounded-lg text-center">
      <div
        className="w-16 h-16 rounded-xl mx-auto mb-4 flex items-center justify-center"
        style={{ backgroundColor: "rgba(61, 142, 255, 0.1)" }}
      >
        <BarChart3 size={28} style={{ color: "var(--color-accent)" }} />
      </div>
      <h3
        className="font-display text-lg font-semibold mb-2"
        style={{ color: "var(--color-text-primary)" }}
      >
        No Intelligence Reports Yet
      </h3>
      <p
        className="text-sm max-w-md mx-auto"
        style={{ color: "var(--color-text-secondary)" }}
      >
        Intelligence reports are generated from your closed trades. Complete some
        trades and check back to see weekly analysis with pair performance,
        session insights, and actionable recommendations.
      </p>
    </div>
  );
}

/* ── Loading Skeleton ─────────────────────────────────────── */

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="glass p-5 rounded-lg animate-pulse">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-lg"
              style={{ backgroundColor: "rgba(61, 142, 255, 0.08)" }}
            />
            <div className="flex-1">
              <div
                className="h-4 w-48 rounded mb-2"
                style={{ backgroundColor: "rgba(138, 155, 192, 0.15)" }}
              />
              <div
                className="h-3 w-32 rounded"
                style={{ backgroundColor: "rgba(138, 155, 192, 0.1)" }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────────── */

export default function IntelligencePage() {
  const [reports, setReports] = useState<WeeklyReport[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchReports() {
      try {
        const res = await fetch("/api/intelligence");
        if (!res.ok) return;
        const data = (await res.json()) as { reports: WeeklyReport[] };
        if (!cancelled) {
          setReports(data.reports ?? []);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchReports();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      {/* Page Header */}
      <div className="mb-6">
        <h1
          className="font-display text-2xl font-bold"
          style={{ color: "var(--color-text-primary)" }}
        >
          Market Intelligence
        </h1>
        <p
          className="text-sm mt-1"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Weekly performance analysis with actionable trading insights
        </p>
      </div>

      {/* Content */}
      {loading ? (
        <LoadingSkeleton />
      ) : reports.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-4">
          {reports.map((report, i) => (
            <ReportCard key={report.weekStart} report={report} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
