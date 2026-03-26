"use client";

import { useRef, useEffect, useState } from "react";
import { useAgentEvents, type AgentEvent } from "@/hooks/useAgentEvents";

// ── Agent registry ──────────────────────────────────────────
const AGENTS: Record<string, { tag: string; color: string }> = {
  SCANNER:      { tag: "SCAN", color: "#3D8EFF" },
  CLAUDE:       { tag: "CLDE", color: "#D4A574" },
  "SA-01":      { tag: "SA01", color: "#6C9CE8" },
  "SA-02":      { tag: "SA02", color: "#9B7ED8" },
  "SA-03":      { tag: "SA03", color: "#FFB347" },
  RISK_ENGINE:  { tag: "RISK", color: "#FFB347" },
  EXECUTION:    { tag: "EXEC", color: "#00C896" },
  CONSENSUS:    { tag: "CONS", color: "#E8A06C" },
};

const SEVERITY_COLOR: Record<string, string> = {
  SUCCESS: "#00C896",
  WARNING: "#FFB347",
  ERROR:   "#FF4D6A",
  INFO:    "#3D8EFF",
};

// ── Timestamp formatter (UTC, consistent with all other displays) ───
function formatTimeUTC(ts: string): string {
  try {
    const d = new Date(ts);
    const hh = d.getUTCHours().toString().padStart(2, "0");
    const mm = d.getUTCMinutes().toString().padStart(2, "0");
    const ss = d.getUTCSeconds().toString().padStart(2, "0");
    return `${hh}:${mm}:${ss}`;
  } catch {
    return "??:??:??";
  }
}

// ── Single event row ────────────────────────────────────────
function EventRow({ event, isNew }: { event: AgentEvent; isNew: boolean }) {
  const agent = AGENTS[event.agent] || { tag: "????", color: "#8A9BC0" };
  const sevColor = SEVERITY_COLOR[event.severity] || SEVERITY_COLOR.INFO;

  return (
    <div
      className={`flex items-start gap-0 font-mono text-[11px] leading-[18px] border-l-2 transition-all duration-500 ${isNew ? "bg-[#0A1628]" : ""}`}
      style={{ borderLeftColor: sevColor }}
    >
      {/* Timestamp */}
      <span className="shrink-0 w-[68px] px-2 py-[3px] text-[#4A5E80] select-none">
        {formatTimeUTC(event.created_at)}
      </span>

      {/* Agent tag */}
      <span
        className="shrink-0 w-[42px] py-[3px] font-bold text-center select-none"
        style={{ color: agent.color }}
      >
        {agent.tag}
      </span>

      {/* Pair */}
      <span className="shrink-0 w-[62px] py-[3px] text-[#6B7280] text-center">
        {event.pair ? event.pair.replace("_", "/") : "──────"}
      </span>

      {/* Message */}
      <span className="flex-1 py-[3px] pr-2 text-[#C9D1D9] truncate">
        {event.title}
      </span>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────
export default function MissionControl() {
  const { events, loading } = useAgentEvents();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const prevCountRef = useRef(0);

  // Flash new events
  useEffect(() => {
    if (events.length > prevCountRef.current) {
      const fresh = new Set(events.slice(0, events.length - prevCountRef.current).map(e => e.id));
      setNewIds(fresh);
      const t = setTimeout(() => setNewIds(new Set()), 1500);
      prevCountRef.current = events.length;
      return () => clearTimeout(t);
    }
    prevCountRef.current = events.length;
  }, [events]);

  if (loading) {
    return (
      <div className="h-[420px]" style={{ background: "#060D18", border: "1px solid #1E3050" }}>
        <div className="px-3 py-2 border-b" style={{ borderColor: "#1E3050" }}>
          <div className="h-3 w-32 bg-[#1E3050] animate-pulse" />
        </div>
        <div className="p-3 space-y-1">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-[18px] bg-[#0A1628] animate-pulse" style={{ width: `${70 + Math.random() * 30}%` }} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: "#060D18", border: "1px solid #1E3050" }}>
      {/* Header bar */}
      <div
        className="flex items-center justify-between px-3 py-1.5"
        style={{ borderBottom: "1px solid #1E3050", background: "#0A1220" }}
      >
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] font-bold tracking-widest" style={{ color: "#3D8EFF" }}>
            MISSION CONTROL
          </span>
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-50" style={{ background: "#00C896" }} />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full" style={{ background: "#00C896" }} />
          </span>
          <span className="font-mono text-[9px] font-bold" style={{ color: "#00C896" }}>
            LIVE
          </span>
        </div>
        <span className="font-mono text-[9px]" style={{ color: "#4A5E80" }}>
          {events.length} EVT
        </span>
      </div>

      {/* Column headers */}
      <div
        className="flex items-center gap-0 font-mono text-[9px] tracking-wider px-0 py-1"
        style={{ borderBottom: "1px solid #121D2E", color: "#4A5E80", background: "#080F1C" }}
      >
        <span className="w-[70px] px-2">TIME</span>
        <span className="w-[42px] text-center">AGENT</span>
        <span className="w-[62px] text-center">PAIR</span>
        <span className="flex-1 pr-2">EVENT</span>
      </div>

      {/* Event feed */}
      <div
        ref={scrollRef}
        className="overflow-y-auto"
        style={{ maxHeight: "380px" }}
      >
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 font-mono">
            <span className="text-[11px] mb-1" style={{ color: "#4A5E80" }}>
              ▓▓▓ AWAITING SIGNAL ▓▓▓
            </span>
            <span className="text-[10px]" style={{ color: "#2A3A50" }}>
              Agent activity will stream here in real-time
            </span>
          </div>
        ) : (
          <div className="divide-y" style={{ borderColor: "#0D1825" }}>
            {events.map((event) => (
              <EventRow key={event.id} event={event} isNew={newIds.has(event.id)} />
            ))}
          </div>
        )}
      </div>

      {/* Footer — agent legend */}
      <div
        className="flex items-center gap-3 px-3 py-1"
        style={{ borderTop: "1px solid #1E3050", background: "#080F1C" }}
      >
        {Object.entries(AGENTS)
          .filter(([k]) => ["SCANNER", "CLAUDE", "RISK_ENGINE", "EXECUTION", "SA-01", "SA-03"].includes(k))
          .map(([, agent]) => (
            <span key={agent.tag} className="font-mono text-[8px] font-bold" style={{ color: agent.color }}>
              {agent.tag}
            </span>
          ))}
      </div>
    </div>
  );
}
