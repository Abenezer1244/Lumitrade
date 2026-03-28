"use client";

import { useSystemStatus } from "@/hooks/useSystemStatus";
import { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence, useMotionValue, useTransform, animate } from "motion/react";
import type { ComponentStatus } from "@/types/system";

/* ── Animated number ───────────────────────────────────────── */

function AnimatedNumber({ value, suffix = "", className }: { value: number; suffix?: string; className?: string }) {
  const motionVal = useMotionValue(value);
  const displayed = useTransform(motionVal, (v) => Math.round(v));
  const [current, setCurrent] = useState(value);

  useEffect(() => {
    const controls = animate(motionVal, value, {
      duration: 0.5,
      ease: [0.16, 1, 0.3, 1],
    });
    const unsub = displayed.on("change", (v) => setCurrent(v));
    return () => { controls.stop(); unsub(); };
  }, [value, motionVal, displayed]);

  return <span className={className}>{current}{suffix}</span>;
}

/* ── Status indicator dot ──────────────────────────────────── */

function StatusDot({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    ok: "#00C896", healthy: "#00C896", online: "#00C896", closed: "#00C896",
    degraded: "#FFB347", warning: "#FFB347", half_open: "#FFB347",
    offline: "#FF4D6A", error: "#FF4D6A", open: "#FF4D6A",
  };
  const color = colorMap[status] ?? "var(--color-text-tertiary)";
  const isHealthy = ["ok", "healthy", "online", "closed"].includes(status);

  return (
    <span className="relative flex h-1.5 w-1.5">
      {!isHealthy && (
        <motion.span
          className="absolute inline-flex h-full w-full rounded-full"
          style={{ backgroundColor: color }}
          animate={{ scale: [1, 2, 1], opacity: [0.6, 0, 0.6] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      <span className="relative inline-flex rounded-full h-1.5 w-1.5" style={{ backgroundColor: color }} />
    </span>
  );
}

/* ── Overall status badge ──────────────────────────────────── */

function OverallBadge({ status }: { status: "healthy" | "degraded" | "offline" }) {
  const styles: Record<string, { bg: string; color: string }> = {
    healthy:  { bg: "rgba(0, 200, 150, 0.1)", color: "var(--color-profit)" },
    degraded: { bg: "rgba(255, 179, 71, 0.1)", color: "var(--color-warning)" },
    offline:  { bg: "rgba(255, 77, 106, 0.1)", color: "var(--color-loss)" },
  };
  const s = styles[status] || styles.offline;

  return (
    <AnimatePresence mode="wait">
      <motion.span
        key={status}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-widest"
        style={{ background: s.bg, color: s.color }}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        transition={{ duration: 0.2 }}
      >
        <span className="w-1 h-1 rounded-full" style={{ backgroundColor: s.color }} />
        {status}
      </motion.span>
    </AnimatePresence>
  );
}

/* ── Component info shape ──────────────────────────────────── */

interface ComponentInfo {
  label: string;
  status: string;
  detail: string;
  numericValue?: number;
  numericSuffix?: string;
}

/* ── Main panel — muted glass, compact ─────────────────────── */

export default function SystemStatusPanel() {
  const { health, loading } = useSystemStatus();

  if (loading || !health) {
    return (
      <div className="glass-muted p-5 h-[220px]">
        <div className="animate-pulse space-y-2.5">
          <div className="flex justify-between">
            <div className="h-3 w-20 rounded bg-elevated" />
            <div className="h-3 w-14 rounded bg-elevated" />
          </div>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex justify-between">
              <div className="h-2 w-16 rounded bg-elevated" />
              <div className="h-2 w-10 rounded bg-elevated" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const components: ComponentInfo[] = [
    {
      label: "OANDA API",
      status: health.components.oanda_api.status,
      detail: `${health.components.oanda_api.latency_ms}ms`,
      numericValue: health.components.oanda_api.latency_ms,
      numericSuffix: "ms",
    },
    {
      label: "AI Brain",
      status: health.components.ai_brain.status,
      detail: `${health.components.ai_brain.last_call_ago_s}s ago`,
      numericValue: health.components.ai_brain.last_call_ago_s,
      numericSuffix: "s ago",
    },
    {
      label: "Database",
      status: health.components.database.status,
      detail: `${health.components.database.latency_ms}ms`,
      numericValue: health.components.database.latency_ms,
      numericSuffix: "ms",
    },
    {
      label: "Price Feed",
      status: health.components.price_feed.status,
      detail: `${health.components.price_feed.last_tick_ago_s}s ago`,
      numericValue: health.components.price_feed.last_tick_ago_s,
      numericSuffix: "s ago",
    },
    {
      label: "Risk Engine",
      status: health.components.risk_engine.status,
      detail: health.components.risk_engine.state,
    },
    {
      label: "Circuit Breaker",
      status: health.components.circuit_breaker.status,
      detail: health.components.circuit_breaker.status.toUpperCase(),
    },
  ];

  const hours = Math.floor(health.uptime_seconds / 3600);
  const minutes = Math.floor((health.uptime_seconds % 3600) / 60);

  return (
    <motion.div
      className="glass-muted p-5 h-full"
      aria-live="polite"
      aria-atomic="true"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-label" style={{ color: "var(--color-text-tertiary)" }}>Status</span>
        <OverallBadge status={health.status} />
      </div>

      {/* Component rows — tight layout */}
      <div className="space-y-2">
        {components.map(({ label, status, detail, numericValue, numericSuffix }, index) => (
          <motion.div
            key={label}
            className="flex items-center justify-between"
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.25, delay: index * 0.04 }}
          >
            <div className="flex items-center gap-2">
              <StatusDot status={status} />
              <span className="text-[11px]" style={{ color: "var(--color-text-secondary)" }}>{label}</span>
            </div>
            {numericValue !== undefined && numericSuffix !== undefined ? (
              <span className="text-[10px] font-mono tabular-nums" style={{ color: "var(--color-text-tertiary)" }}>
                <AnimatedNumber value={numericValue} className="text-[10px] font-mono" />
                {numericSuffix}
              </span>
            ) : (
              <span className="text-[10px] font-mono" style={{ color: "var(--color-text-tertiary)" }}>
                {detail}
              </span>
            )}
          </motion.div>
        ))}
      </div>

      {/* Uptime — subtle footer */}
      <div
        className="mt-3 pt-2.5 flex items-center justify-between"
        style={{ borderTop: "1px solid rgba(30, 55, 92, 0.2)" }}
      >
        <span className="text-[10px]" style={{ color: "var(--color-text-tertiary)" }}>Uptime</span>
        <span className="text-[10px] font-mono tabular-nums" style={{ color: "var(--color-text-tertiary)" }}>
          {hours}h {minutes}m
        </span>
      </div>
    </motion.div>
  );
}
