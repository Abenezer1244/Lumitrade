"use client";

import { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Radio, Activity, Zap, Shield, Brain, Target, Eye, MessageSquare } from "lucide-react";
import { useAgentEvents, type AgentEvent } from "@/hooks/useAgentEvents";

/* ── Agent registry ────────────────────────────────────────── */
const AGENTS: Record<string, { tag: string; color: string; icon: typeof Radio }> = {
  SCANNER:      { tag: "SCAN", color: "#3D8EFF", icon: Radio },
  CLAUDE:       { tag: "CLDE", color: "#D4A574", icon: Brain },
  "SA-01":      { tag: "SA01", color: "#6C9CE8", icon: Eye },
  "SA-02":      { tag: "SA02", color: "#9B7ED8", icon: Activity },
  "SA-03":      { tag: "SA03", color: "#FFB347", icon: Shield },
  RISK_ENGINE:  { tag: "RISK", color: "#FFB347", icon: Shield },
  EXECUTION:    { tag: "EXEC", color: "#00C896", icon: Target },
  CONSENSUS:    { tag: "CONS", color: "#E8A06C", icon: MessageSquare },
  SENTIMENT:    { tag: "SENT", color: "#9B7ED8", icon: Zap },
};

const SEVERITY_STYLES: Record<string, { border: string; bg: string; glow: string }> = {
  SUCCESS: { border: "#00C896", bg: "rgba(0, 200, 150, 0.04)", glow: "rgba(0, 200, 150, 0.12)" },
  WARNING: { border: "#FFB347", bg: "rgba(255, 179, 71, 0.04)", glow: "rgba(255, 179, 71, 0.12)" },
  ERROR:   { border: "#FF4D6A", bg: "rgba(255, 77, 106, 0.04)", glow: "rgba(255, 77, 106, 0.12)" },
  INFO:    { border: "#3D8EFF", bg: "rgba(61, 142, 255, 0.03)", glow: "rgba(61, 142, 255, 0.08)" },
};

function formatTimeUTC(ts: string): string {
  try {
    const d = new Date(ts);
    return `${d.getUTCHours().toString().padStart(2, "0")}:${d.getUTCMinutes().toString().padStart(2, "0")}:${d.getUTCSeconds().toString().padStart(2, "0")}`;
  } catch { return "??:??:??"; }
}

/* ── Event Row ─────────────────────────────────────────────── */

function EventRow({ event, isNew }: { event: AgentEvent; isNew: boolean }) {
  const agent = AGENTS[event.agent] || { tag: "????", color: "var(--color-text-tertiary)", icon: Activity };
  const severity = SEVERITY_STYLES[event.severity] || SEVERITY_STYLES.INFO;
  const Icon = agent.icon;
  const [expanded, setExpanded] = useState(false);
  const hasDetail = event.detail && event.detail.trim().length > 0;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -16, height: 0 }}
      animate={{ opacity: 1, x: 0, height: "auto" }}
      exit={{ opacity: 0, x: 16, height: 0 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      className="overflow-hidden"
    >
      <div
        className={`flex items-center gap-2.5 px-3 py-2 border-l-2 transition-all duration-500 ${hasDetail ? "cursor-pointer" : ""}`}
        style={{
          borderLeftColor: severity.border,
          backgroundColor: isNew ? severity.glow : expanded ? severity.bg : "transparent",
        }}
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        <span className="shrink-0 font-mono text-[10px] tabular-nums" style={{ color: "var(--color-text-tertiary)" }}>
          {formatTimeUTC(event.created_at)}
        </span>
        <div className="shrink-0 flex items-center gap-1">
          <div
            className="w-4 h-4 rounded flex items-center justify-center"
            style={{ backgroundColor: `${agent.color}12` }}
          >
            <Icon size={10} style={{ color: agent.color }} />
          </div>
          <span className="font-mono text-[9px] font-bold tracking-wide" style={{ color: agent.color }}>
            {agent.tag}
          </span>
        </div>
        {event.pair && (
          <span
            className="shrink-0 px-1.5 py-0.5 rounded text-[9px] font-mono font-medium"
            style={{ backgroundColor: "rgba(18, 30, 52, 0.6)", color: "var(--color-text-secondary)" }}
          >
            {event.pair.replace("_", "/")}
          </span>
        )}
        <span className="flex-1 text-[11px] truncate" style={{ color: "var(--color-text-primary)" }}>
          {event.title}
        </span>
        {hasDetail && (
          <motion.span
            className="shrink-0 text-[9px]"
            style={{ color: "var(--color-text-tertiary)" }}
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            ▼
          </motion.span>
        )}
      </div>
      <AnimatePresence>
        {expanded && hasDetail && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div
              className="px-4 py-2 ml-[60px] text-[11px] leading-relaxed whitespace-pre-wrap"
              style={{ color: "var(--color-text-secondary)", backgroundColor: severity.bg, borderLeft: `2px solid ${severity.border}` }}
            >
              {event.detail}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/* ── Market hours check ────────────────────────────────────── */

function useMarketOpen(): boolean {
  const [isOpen, setIsOpen] = useState(() => checkMarketOpen());
  useEffect(() => {
    const interval = setInterval(() => setIsOpen(checkMarketOpen()), 60000);
    return () => clearInterval(interval);
  }, []);
  return isOpen;
}

function checkMarketOpen(): boolean {
  const now = new Date();
  const utcDay = now.getUTCDay();
  const utcHour = now.getUTCHours();
  if (utcDay === 6) return false;
  if (utcDay === 0 && utcHour < 22) return false;
  if (utcDay === 5 && utcHour >= 22) return false;
  return true;
}

/* ── Main Component ────────────────────────────────────────── */

export default function MissionControl() {
  const { events, loading } = useAgentEvents();
  const marketOpen = useMarketOpen();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const prevCountRef = useRef(0);

  useEffect(() => {
    if (events.length > prevCountRef.current) {
      const fresh = new Set(events.slice(0, events.length - prevCountRef.current).map(e => e.id));
      setNewIds(fresh);
      const t = setTimeout(() => setNewIds(new Set()), 2000);
      prevCountRef.current = events.length;
      return () => clearTimeout(t);
    }
    prevCountRef.current = events.length;
  }, [events]);

  if (loading) {
    return (
      <div className="glass overflow-hidden">
        <div className="px-4 py-3" style={{ borderBottom: "1px solid rgba(30, 55, 92, 0.25)" }}>
          <div className="h-4 w-32 rounded bg-elevated" />
        </div>
        <div className="p-3 space-y-2">
          {[...Array(5)].map((_, i) => (
            <motion.div
              key={i}
              className="h-7 rounded"
              style={{ backgroundColor: "var(--color-bg-elevated)", width: `${55 + Math.random() * 45}%` }}
              animate={{ opacity: [0.3, 0.5, 0.3] }}
              transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.12 }}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <motion.div
      className="glass overflow-hidden"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2.5"
        style={{ borderBottom: "1px solid rgba(30, 55, 92, 0.25)" }}
      >
        <div className="flex items-center gap-2">
          <motion.div
            className="flex items-center justify-center w-5 h-5 rounded"
            style={{ background: "var(--gradient-accent-subtle)" }}
          >
            <Radio size={11} style={{ color: "var(--color-accent)" }} />
          </motion.div>
          <span className="text-card-title" style={{ color: "var(--color-text-primary)" }}>
            Mission Control
          </span>
          {marketOpen ? (
            <span
              className="flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[8px] font-bold tracking-widest"
              style={{ background: "rgba(0, 200, 150, 0.1)", color: "var(--color-profit)" }}
            >
              <span className="w-1 h-1 rounded-full" style={{ backgroundColor: "var(--color-profit)" }} />
              LIVE
            </span>
          ) : (
            <span
              className="flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[8px] font-bold tracking-widest"
              style={{ background: "rgba(255, 77, 106, 0.1)", color: "var(--color-loss)" }}
            >
              <span className="w-1 h-1 rounded-full" style={{ backgroundColor: "var(--color-loss)" }} />
              CLOSED
            </span>
          )}
        </div>
        <span className="text-[10px] font-mono tabular-nums" style={{ color: "var(--color-text-tertiary)" }}>
          {events.length}
        </span>
      </div>

      {/* Event feed */}
      <div ref={scrollRef} className="overflow-y-auto scrollbar-hide" style={{ maxHeight: "360px" }}>
        {events.length === 0 ? (
          <motion.div
            className="flex flex-col items-center justify-center py-14 gap-2"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
            >
              <Radio size={20} style={{ color: "var(--color-text-tertiary)", opacity: 0.3 }} />
            </motion.div>
            <span className="text-[11px]" style={{ color: "var(--color-text-tertiary)" }}>
              Awaiting agent activity...
            </span>
          </motion.div>
        ) : (
          <AnimatePresence initial={false}>
            {events.map((event) => (
              <EventRow key={event.id} event={event} isNew={newIds.has(event.id)} />
            ))}
          </AnimatePresence>
        )}
      </div>

      {/* Agent legend — compact */}
      <div
        className="flex items-center gap-1.5 px-3 py-2 overflow-x-auto scrollbar-hide"
        style={{ borderTop: "1px solid rgba(30, 55, 92, 0.2)" }}
      >
        {Object.entries(AGENTS)
          .filter(([k]) => ["SCANNER", "CLAUDE", "RISK_ENGINE", "EXECUTION", "SA-01", "SA-03"].includes(k))
          .map(([, agent]) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.tag}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded-full"
                style={{ backgroundColor: `${agent.color}08` }}
              >
                <Icon size={8} style={{ color: agent.color }} />
                <span className="font-mono text-[7px] font-bold" style={{ color: agent.color }}>
                  {agent.tag}
                </span>
              </div>
            );
          })}
      </div>
    </motion.div>
  );
}
