"use client";

import { useSystemStatus } from "@/hooks/useSystemStatus";
import { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence, useMotionValue, useTransform, animate } from "motion/react";
import { Cpu } from "lucide-react";
import type { ComponentStatus } from "@/types/system";

/* ------------------------------------------------------------------ */
/*  Animated number display — smoothly transitions between values     */
/* ------------------------------------------------------------------ */

interface AnimatedNumberProps {
  value: number;
  suffix?: string;
  className?: string;
}

function AnimatedNumber({ value, suffix = "", className }: AnimatedNumberProps) {
  const motionVal = useMotionValue(value);
  const displayed = useTransform(motionVal, (v) => Math.round(v));
  const [current, setCurrent] = useState(value);

  useEffect(() => {
    const controls = animate(motionVal, value, {
      duration: 0.6,
      ease: [0.25, 0.46, 0.45, 0.94],
    });
    const unsub = displayed.on("change", (v) => setCurrent(v));
    return () => {
      controls.stop();
      unsub();
    };
  }, [value, motionVal, displayed]);

  return <span className={className}>{current}{suffix}</span>;
}

/* ------------------------------------------------------------------ */
/*  Pulse dot — animated ping ring for live status indication         */
/* ------------------------------------------------------------------ */

interface PulseDotProps {
  status: string;
}

function PulseDot({ status }: PulseDotProps) {
  const colorMap: Record<string, { bg: string; ring: string }> = {
    ok:        { bg: "bg-profit",  ring: "bg-profit" },
    healthy:   { bg: "bg-profit",  ring: "bg-profit" },
    online:    { bg: "bg-profit",  ring: "bg-profit" },
    closed:    { bg: "bg-profit",  ring: "bg-profit" },
    degraded:  { bg: "bg-warning", ring: "bg-warning" },
    warning:   { bg: "bg-warning", ring: "bg-warning" },
    half_open: { bg: "bg-warning", ring: "bg-warning" },
    offline:   { bg: "bg-loss",    ring: "bg-loss" },
    error:     { bg: "bg-loss",    ring: "bg-loss" },
    open:      { bg: "bg-loss",    ring: "bg-loss" },
  };

  const colors = colorMap[status] ?? { bg: "bg-tertiary", ring: "bg-tertiary" };

  return (
    <span className="relative flex h-2 w-2">
      <motion.span
        className={`absolute inline-flex h-full w-full rounded-full ${colors.ring} opacity-75`}
        animate={{ scale: [1, 1.8, 1], opacity: [0.75, 0, 0.75] }}
        transition={{
          duration: status === "ok" || status === "healthy" || status === "closed" ? 2.4 : 1.2,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      <span className={`relative inline-flex rounded-full h-2 w-2 ${colors.bg}`} />
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Overall status badge with color transition                        */
/* ------------------------------------------------------------------ */

interface StatusBadgeProps {
  status: "healthy" | "degraded" | "offline";
}

function StatusBadge({ status }: StatusBadgeProps) {
  const colorMap: Record<string, string> = {
    healthy:  "text-profit",
    degraded: "text-warning",
    offline:  "text-loss",
  };

  const bgMap: Record<string, string> = {
    healthy:  "bg-profit/10",
    degraded: "bg-warning/10",
    offline:  "bg-loss/10",
  };

  return (
    <AnimatePresence mode="wait">
      <motion.span
        key={status}
        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${colorMap[status]} ${bgMap[status]}`}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
      >
        <span className="relative flex h-1.5 w-1.5">
          <motion.span
            className={`absolute inline-flex h-full w-full rounded-full ${status === "healthy" ? "bg-profit" : status === "degraded" ? "bg-warning" : "bg-loss"}`}
            animate={{ opacity: [1, 0.4, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          />
        </span>
        {status}
      </motion.span>
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------------ */
/*  Uptime display with animated hour/minute counters                 */
/* ------------------------------------------------------------------ */

interface UptimeDisplayProps {
  uptimeSeconds: number;
}

function UptimeDisplay({ uptimeSeconds }: UptimeDisplayProps) {
  const hours = Math.floor(uptimeSeconds / 3600);
  const minutes = Math.floor((uptimeSeconds % 3600) / 60);

  return (
    <span className="text-[10px] font-mono text-secondary tabular-nums">
      <AnimatedNumber value={hours} className="text-[10px] font-mono text-secondary" />
      <span>h </span>
      <AnimatedNumber value={minutes} className="text-[10px] font-mono text-secondary" />
      <span>m</span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Component row data shape                                          */
/* ------------------------------------------------------------------ */

interface ComponentInfo {
  label: string;
  status: string;
  detail: string;
  numericValue?: number;
  numericSuffix?: string;
}

/* ------------------------------------------------------------------ */
/*  Main panel                                                        */
/* ------------------------------------------------------------------ */

export default function SystemStatusPanel() {
  const { health, loading } = useSystemStatus();
  const prevHealthRef = useRef(health);

  useEffect(() => {
    if (health) {
      prevHealthRef.current = health;
    }
  }, [health]);

  if (loading || !health) {
    return (
      <div className="glass p-5 h-48">
        <div className="animate-pulse space-y-3">
          <div className="flex justify-between">
            <div className="h-3 w-24 rounded bg-elevated" />
            <div className="h-3 w-16 rounded bg-elevated" />
          </div>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex justify-between">
              <div className="h-2.5 w-20 rounded bg-elevated" />
              <div className="h-2.5 w-12 rounded bg-elevated" />
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

  return (
    <motion.div
      className="glass p-5"
      aria-live="polite"
      aria-atomic="true"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-6 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: "var(--color-accent-glow)" }}
          >
            <Cpu size={12} style={{ color: "var(--color-accent)" }} aria-hidden="true" />
          </div>
          <span className="text-label" style={{ color: "var(--color-text-secondary)" }}>System Status</span>
        </div>
        <StatusBadge status={health.status} />
      </div>

      {/* Component rows — staggered entrance */}
      <div className="space-y-2.5">
        {components.map(({ label, status, detail, numericValue, numericSuffix }, index) => (
          <motion.div
            key={label}
            className="flex items-center justify-between"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{
              duration: 0.3,
              delay: index * 0.05,
              ease: "easeOut",
            }}
          >
            <div className="flex items-center gap-2">
              <PulseDot status={status} />
              <span className="text-xs text-primary">{label}</span>
            </div>

            {numericValue !== undefined && numericSuffix !== undefined ? (
              <span className="text-[10px] font-mono text-tertiary tabular-nums">
                <AnimatedNumber
                  value={numericValue}
                  className="text-[10px] font-mono text-tertiary"
                />
                {numericSuffix}
              </span>
            ) : (
              <motion.span
                key={detail}
                className="text-[10px] font-mono text-tertiary"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
              >
                {detail}
              </motion.span>
            )}
          </motion.div>
        ))}
      </div>

      {/* Uptime footer */}
      <motion.div
        className="mt-3 pt-3 border-t border-border flex items-center justify-between"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.35 }}
      >
        <span className="text-[10px] text-tertiary">Uptime</span>
        <UptimeDisplay uptimeSeconds={health.uptime_seconds} />
      </motion.div>
    </motion.div>
  );
}
