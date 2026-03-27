"use client";

import { useMemo } from "react";
import { motion } from "motion/react";
import { Radio, Check, Minus } from "lucide-react";
import { useAgentEvents, type AgentEvent } from "@/hooks/useAgentEvents";

function formatTime(ts: string): string {
  try {
    const d = new Date(ts);
    return `${d.getUTCHours().toString().padStart(2, "0")}:${d.getUTCMinutes().toString().padStart(2, "0")}`;
  } catch {
    return "??:??";
  }
}

interface ScanResult {
  time: string;
  pair: string;
  result: "signal" | "hold" | "error";
  detail: string;
}

export default function ScanTimeline() {
  const { events } = useAgentEvents();

  const scans = useMemo(() => {
    return events
      .filter((e) => e.agent === "SCANNER" || (e.agent === "CLAUDE" && e.event_type === "SIGNAL"))
      .slice(0, 16)
      .map((e): ScanResult => {
        let result: "signal" | "hold" | "error" = "hold";
        if (e.agent === "CLAUDE") result = "signal";
        if (e.title?.includes("error") || e.severity === "ERROR") result = "error";
        return {
          time: e.created_at,
          pair: e.pair || "",
          result,
          detail: e.title || "",
        };
      });
  }, [events]);

  if (scans.length === 0) return null;

  return (
    <motion.div
      className="glass p-4"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Radio size={13} style={{ color: "var(--color-accent)" }} />
        <h3 className="text-[12px] font-semibold" style={{ color: "var(--color-text-primary)" }}>
          Recent Scans
        </h3>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {scans.map((scan, idx) => {
          const bgColor =
            scan.result === "signal" ? "var(--color-profit-dim)" :
            scan.result === "error" ? "var(--color-loss-dim)" :
            "var(--color-bg-elevated)";
          const iconColor =
            scan.result === "signal" ? "var(--color-profit)" :
            scan.result === "error" ? "var(--color-loss)" :
            "var(--color-text-tertiary)";

          return (
            <motion.div
              key={`${scan.time}-${idx}`}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: idx * 0.03 }}
              className="flex items-center gap-1 px-2 py-1 rounded cursor-default group relative"
              style={{ backgroundColor: bgColor }}
              title={scan.detail}
            >
              {scan.result === "signal" ? (
                <Check size={9} style={{ color: iconColor }} />
              ) : (
                <Minus size={9} style={{ color: iconColor }} />
              )}
              <span className="text-[9px] font-mono" style={{ color: "var(--color-text-secondary)" }}>
                {scan.pair ? scan.pair.replace("_", "/").split("/")[0] : ""}
              </span>
              <span className="text-[8px] font-mono" style={{ color: "var(--color-text-tertiary)" }}>
                {formatTime(scan.time)}
              </span>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}
