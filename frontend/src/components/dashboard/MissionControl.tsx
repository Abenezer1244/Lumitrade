"use client";

import { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Radio, Activity, Zap, Shield, Brain, Target, Eye, MessageSquare } from "lucide-react";
import { useAgentEvents, type AgentEvent } from "@/hooks/useAgentEvents";

// ── Agent registry with icons ──────────────────────────────
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
  SUCCESS: { border: "#00C896", bg: "rgba(0, 200, 150, 0.06)", glow: "rgba(0, 200, 150, 0.15)" },
  WARNING: { border: "#FFB347", bg: "rgba(255, 179, 71, 0.06)", glow: "rgba(255, 179, 71, 0.15)" },
  ERROR:   { border: "#FF4D6A", bg: "rgba(255, 77, 106, 0.06)", glow: "rgba(255, 77, 106, 0.15)" },
  INFO:    { border: "#3D8EFF", bg: "rgba(61, 142, 255, 0.04)", glow: "rgba(61, 142, 255, 0.1)" },
};

function formatTimeUTC(ts: string): string {
  try {
    const d = new Date(ts);
    return `${d.getUTCHours().toString().padStart(2, "0")}:${d.getUTCMinutes().toString().padStart(2, "0")}:${d.getUTCSeconds().toString().padStart(2, "0")}`;
  } catch {
    return "??:??:??";
  }
}

// ── Animated event row ─────────────────────────────────────
function EventRow({ event, isNew }: { event: AgentEvent; isNew: boolean }) {
  const agent = AGENTS[event.agent] || { tag: "????", color: "var(--color-text-tertiary)", icon: Activity };
  const severity = SEVERITY_STYLES[event.severity] || SEVERITY_STYLES.INFO;
  const Icon = agent.icon;
  const [expanded, setExpanded] = useState(false);
  const hasDetail = event.detail && event.detail.trim().length > 0;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -20, height: 0 }}
      animate={{ opacity: 1, x: 0, height: "auto" }}
      exit={{ opacity: 0, x: 20, height: 0 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      className="overflow-hidden"
    >
      <div
        className={`flex items-center gap-3 px-3 py-2 border-l-2 transition-all duration-700 ${hasDetail ? "cursor-pointer" : ""}`}
        style={{
          borderLeftColor: severity.border,
          backgroundColor: isNew ? severity.glow : expanded ? severity.bg : "transparent",
        }}
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        {/* Timestamp */}
        <span className="shrink-0 font-mono text-[10px] tabular-nums" style={{ color: "var(--color-text-tertiary)" }}>
          {formatTimeUTC(event.created_at)}
        </span>

        {/* Agent icon + tag */}
        <div className="shrink-0 flex items-center gap-1.5">
          <div
            className="w-5 h-5 rounded flex items-center justify-center"
            style={{ backgroundColor: `${agent.color}15` }}
          >
            <Icon size={11} style={{ color: agent.color }} />
          </div>
          <span
            className="font-mono text-[10px] font-bold tracking-wide"
            style={{ color: agent.color }}
          >
            {agent.tag}
          </span>
        </div>

        {/* Pair badge */}
        {event.pair ? (
          <span
            className="shrink-0 px-1.5 py-0.5 rounded text-[9px] font-mono font-medium"
            style={{
              backgroundColor: "var(--color-bg-elevated)",
              color: "var(--color-text-secondary)",
            }}
          >
            {event.pair.replace("_", "/")}
          </span>
        ) : (
          <span className="shrink-0 w-[52px]" />
        )}

        {/* Message */}
        <span
          className="flex-1 text-[11px] truncate"
          style={{ color: "var(--color-text-primary)" }}
        >
          {event.title}
        </span>

        {/* Expand indicator */}
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

      {/* Expandable detail */}
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
              className="px-4 py-2 ml-[68px] text-[11px] leading-relaxed whitespace-pre-wrap"
              style={{
                color: "var(--color-text-secondary)",
                backgroundColor: severity.bg,
                borderLeft: `2px solid ${severity.border}`,
              }}
            >
              {event.detail}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Pulse dot ──────────────────────────────────────────────
function PulseDot({ color }: { color: string }) {
  return (
    <span className="relative flex h-2 w-2">
      <motion.span
        className="absolute inline-flex h-full w-full rounded-full"
        style={{ backgroundColor: color, opacity: 0.5 }}
        animate={{ scale: [1, 1.8, 1], opacity: [0.5, 0, 0.5] }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      />
      <span
        className="relative inline-flex h-2 w-2 rounded-full"
        style={{ backgroundColor: color }}
      />
    </span>
  );
}

// ── Market hours check ────────────────────────────────────
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
  const utcDay = now.getUTCDay(); // 0=Sun, 5=Fri, 6=Sat
  const utcHour = now.getUTCHours();

  if (utcDay === 6) return false; // Saturday
  if (utcDay === 0 && utcHour < 22) return false; // Sunday before 22:00
  if (utcDay === 5 && utcHour >= 22) return false; // Friday after 22:00
  return true;
}

// ── Main component ─────────────────────────────────────────
export default function MissionControl() {
  const { events, loading } = useAgentEvents();
  const marketOpen = useMarketOpen();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const prevCountRef = useRef(0);

  // Flash new events
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
        <div className="px-4 py-3 border-b" style={{ borderColor: "var(--color-border)" }}>
          <div className="h-4 w-36 rounded" style={{ backgroundColor: "var(--color-bg-elevated)" }} />
        </div>
        <div className="p-3 space-y-2">
          {[...Array(6)].map((_, i) => (
            <motion.div
              key={i}
              className="h-8 rounded"
              style={{ backgroundColor: "var(--color-bg-elevated)", width: `${60 + Math.random() * 40}%` }}
              animate={{ opacity: [0.3, 0.6, 0.3] }}
              transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.15 }}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <motion.div
      className="glass overflow-hidden"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2.5"
        style={{ borderBottom: `1px solid var(--color-border)` }}
      >
        <div className="flex items-center gap-2.5">
          <motion.div
            className="flex items-center justify-center w-6 h-6 rounded-md"
            style={{ backgroundColor: "var(--color-accent-glow)" }}
            animate={{ rotate: [0, 5, -5, 0] }}
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          >
            <Radio size={13} style={{ color: "var(--color-accent)" }} />
          </motion.div>
          <span className="text-xs font-semibold tracking-wide" style={{ color: "var(--color-text-primary)" }}>
            Mission Control
          </span>
          {marketOpen ? (
            <>
              <PulseDot color="var(--color-profit)" />
              <span className="text-[9px] font-bold font-mono" style={{ color: "var(--color-profit)" }}>
                LIVE
              </span>
            </>
          ) : (
            <>
              <span className="relative flex h-2 w-2">
                <span className="relative inline-flex h-2 w-2 rounded-full" style={{ backgroundColor: "var(--color-loss)" }} />
              </span>
              <span className="text-[9px] font-bold font-mono" style={{ color: "var(--color-loss)" }}>
                CLOSED
              </span>
            </>
          )}
        </div>
        <span className="text-[10px] font-mono tabular-nums" style={{ color: "var(--color-text-tertiary)" }}>
          {events.length} events
        </span>
      </div>

      {/* Event feed */}
      <div
        ref={scrollRef}
        className="overflow-y-auto"
        style={{ maxHeight: "380px" }}
      >
        {events.length === 0 ? (
          <motion.div
            className="flex flex-col items-center justify-center py-16 gap-3"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
            >
              <Radio size={24} style={{ color: "var(--color-text-tertiary)", opacity: 0.4 }} />
            </motion.div>
            <span className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
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

      {/* Footer — agent legend */}
      <div
        className="flex items-center gap-2 px-4 py-2 overflow-x-auto scrollbar-hide"
        style={{ borderTop: `1px solid var(--color-border)` }}
      >
        {Object.entries(AGENTS)
          .filter(([k]) => ["SCANNER", "CLAUDE", "RISK_ENGINE", "EXECUTION", "SA-01", "SA-03", "SENTIMENT"].includes(k))
          .map(([, agent]) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.tag}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded"
                style={{ backgroundColor: `${agent.color}10` }}
              >
                <Icon size={9} style={{ color: agent.color }} />
                <span className="font-mono text-[8px] font-bold" style={{ color: agent.color }}>
                  {agent.tag}
                </span>
              </div>
            );
          })}
      </div>

      {/* Bottom gradient fade */}
      <div
        className="absolute bottom-8 left-0 right-0 h-8 pointer-events-none"
        style={{
          background: `linear-gradient(transparent, var(--color-bg-surface-solid))`,
        }}
      />
    </motion.div>
  );
}
