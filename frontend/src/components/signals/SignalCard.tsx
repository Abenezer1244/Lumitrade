"use client";
import { useState } from "react";
import type { Signal } from "@/types/trading";
import { formatPair, formatTime } from "@/lib/formatters";
import Badge from "@/components/ui/Badge";
import ConfidenceBar from "./ConfidenceBar";
import SignalDetailPanel from "./SignalDetailPanel";

interface Props {
  signal: Signal;
}

export default function SignalCard({ signal }: Props) {
  const [expanded, setExpanded] = useState(false);
  const isHold = signal.action === "HOLD";
  const canExpand = !isHold;

  return (
    <div
      className={`glass p-3 transition-colors ${
        canExpand ? "cursor-pointer hover:border-accent/40" : ""
      }`}
      onClick={() => canExpand && setExpanded(!expanded)}
      role={canExpand ? "button" : undefined}
      tabIndex={canExpand ? 0 : undefined}
      onKeyDown={(e) => {
        if (canExpand && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          setExpanded(!expanded);
        }
      }}
      aria-expanded={canExpand ? expanded : undefined}
    >
      {/* Collapsed View */}
      <div className="flex items-center gap-3">
        <span className="text-sm font-mono text-primary font-medium">{formatPair(signal.pair)}</span>
        <Badge action={signal.action} />
        <div className="flex-1 max-w-[120px]">
          <ConfidenceBar value={signal.confidence_adjusted} />
        </div>
        <span className="text-[10px] text-tertiary font-mono shrink-0">{formatTime(signal.created_at)}</span>
        {signal.executed && (
          <span className="text-[10px] font-bold uppercase text-accent px-1.5 py-0.5 bg-accent/10 rounded">Executed</span>
        )}
        {signal.rejection_reason && !signal.executed && (
          <span className="text-[10px] font-bold uppercase text-loss px-1.5 py-0.5 bg-loss-dim rounded">Rejected</span>
        )}
        {canExpand && (
          <svg
            className={`w-4 h-4 text-tertiary transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </div>

      {/* Summary Line */}
      <p className="text-xs text-secondary mt-1.5 line-clamp-1">{signal.summary}</p>

      {/* Expanded Detail Panel */}
      {canExpand && (
        <div
          className="overflow-hidden transition-all duration-200 ease-in-out"
          style={{
            maxHeight: expanded ? "2000px" : "0",
            opacity: expanded ? 1 : 0,
          }}
        >
          <SignalDetailPanel signal={signal} />
        </div>
      )}
    </div>
  );
}
