"use client";

import { useRef, useEffect } from "react";
import {
  Brain,
  Shield,
  Zap,
  BarChart3,
  Eye,
  Radio,
  FileText,
  AlertTriangle,
} from "lucide-react";
import { useAgentEvents, type AgentEvent } from "@/hooks/useAgentEvents";

// Agent identity system — each agent has a distinct icon, color, and label
const AGENTS: Record<
  string,
  { icon: typeof Brain; color: string; bg: string; label: string }
> = {
  SCANNER: {
    icon: Radio,
    color: "text-brand",
    bg: "bg-brand/10",
    label: "Scanner",
  },
  CLAUDE: {
    icon: Brain,
    color: "text-[#D4A574]",
    bg: "bg-[#D4A574]/10",
    label: "Claude AI",
  },
  "SA-01": {
    icon: BarChart3,
    color: "text-[#6C9CE8]",
    bg: "bg-[#6C9CE8]/10",
    label: "Analyst",
  },
  "SA-02": {
    icon: FileText,
    color: "text-[#9B7ED8]",
    bg: "bg-[#9B7ED8]/10",
    label: "Post-Trade",
  },
  "SA-03": {
    icon: Eye,
    color: "text-warning",
    bg: "bg-warning/10",
    label: "Risk Monitor",
  },
  RISK_ENGINE: {
    icon: Shield,
    color: "text-warning",
    bg: "bg-warning/10",
    label: "Risk Engine",
  },
  EXECUTION: {
    icon: Zap,
    color: "text-profit",
    bg: "bg-profit/10",
    label: "Execution",
  },
  CONSENSUS: {
    icon: Brain,
    color: "text-[#E8A06C]",
    bg: "bg-[#E8A06C]/10",
    label: "Consensus",
  },
};

const SEVERITY_STYLES: Record<string, string> = {
  SUCCESS: "border-l-profit",
  WARNING: "border-l-warning",
  ERROR: "border-l-loss",
  INFO: "border-l-brand/40",
};

function LivePulse() {
  return (
    <span className="relative flex h-2 w-2">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-profit opacity-40" />
      <span className="relative inline-flex h-2 w-2 rounded-full bg-profit" />
    </span>
  );
}

function TimeAgo({ timestamp }: { timestamp: string }) {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  let text: string;
  if (diffSec < 5) text = "just now";
  else if (diffSec < 60) text = `${diffSec}s ago`;
  else if (diffSec < 3600) text = `${Math.floor(diffSec / 60)}m ago`;
  else text = date.toLocaleTimeString("en-US", { hour12: false });

  return (
    <span className="text-[10px] text-tertiary font-mono whitespace-nowrap">
      {text}
    </span>
  );
}

function EventRow({ event }: { event: AgentEvent }) {
  const agent = AGENTS[event.agent] || AGENTS.SCANNER;
  const Icon = agent.icon;
  const severityBorder = SEVERITY_STYLES[event.severity] || SEVERITY_STYLES.INFO;

  return (
    <div
      className={`flex gap-3 py-2.5 px-3 border-l-2 ${severityBorder} hover:bg-elevated/30 transition-colors animate-in fade-in slide-in-from-top-1 duration-300`}
    >
      {/* Agent avatar */}
      <div
        className={`flex-shrink-0 w-7 h-7 rounded-md ${agent.bg} flex items-center justify-center mt-0.5`}
      >
        <Icon size={14} className={agent.color} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span
            className={`text-[10px] font-bold uppercase tracking-wider ${agent.color}`}
          >
            {agent.label}
          </span>
          {event.pair && (
            <span className="text-[10px] font-mono text-secondary bg-elevated px-1.5 py-0.5 rounded">
              {event.pair.replace("_", "/")}
            </span>
          )}
          <TimeAgo timestamp={event.created_at} />
        </div>
        <p className="text-xs text-primary leading-relaxed">{event.title}</p>
        {event.detail && (
          <p className="text-[11px] text-tertiary mt-1 leading-relaxed line-clamp-2">
            {event.detail}
          </p>
        )}

        {/* Metadata chips */}
        {event.metadata && Object.keys(event.metadata).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {Object.entries(event.metadata)
              .filter(([, v]) => v !== null && v !== "")
              .slice(0, 4)
              .map(([k, v]) => (
                <span
                  key={k}
                  className="text-[9px] font-mono text-tertiary bg-elevated/50 px-1.5 py-0.5 rounded"
                >
                  {k}: {String(v)}
                </span>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function MissionControl() {
  const { events, loading } = useAgentEvents();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to top when new events arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [events.length]);

  if (loading) {
    return (
      <div className="glass p-5 animate-pulse h-96">
        <div className="h-5 bg-elevated rounded w-40 mb-4" />
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-elevated/50 rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="glass overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border">
        <div className="flex items-center gap-2.5">
          <Radio size={16} className="text-brand" />
          <h3 className="text-card-title text-primary">Mission Control</h3>
          <LivePulse />
          <span className="text-[10px] text-profit font-mono">LIVE</span>
        </div>
        <span className="text-[10px] text-tertiary font-mono">
          {events.length} events
        </span>
      </div>

      {/* Event feed */}
      <div
        ref={scrollRef}
        className="overflow-y-auto max-h-[480px] divide-y divide-border/30"
      >
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <Radio size={24} className="text-tertiary" />
            <p className="text-sm text-tertiary">
              Waiting for agent activity...
            </p>
            <p className="text-xs text-tertiary">
              Events appear here as agents scan, analyze, and trade.
            </p>
          </div>
        ) : (
          events.map((event) => <EventRow key={event.id} event={event} />)
        )}
      </div>

      {/* Footer — agent legend */}
      <div className="px-5 py-2.5 border-t border-border bg-elevated/20">
        <div className="flex flex-wrap gap-3">
          {Object.entries(AGENTS)
            .filter(([key]) =>
              ["SCANNER", "CLAUDE", "SA-01", "RISK_ENGINE", "EXECUTION", "SA-03"].includes(key)
            )
            .map(([key, agent]) => {
              const Icon = agent.icon;
              return (
                <div key={key} className="flex items-center gap-1">
                  <Icon size={10} className={agent.color} />
                  <span className="text-[9px] text-tertiary">
                    {agent.label}
                  </span>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}
