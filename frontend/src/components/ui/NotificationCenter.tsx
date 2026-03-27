"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Bell, X, TrendingUp, TrendingDown, AlertTriangle, Shield, Radio } from "lucide-react";
import { useAgentEvents, type AgentEvent } from "@/hooks/useAgentEvents";

const SEVERITY_ICON: Record<string, typeof Bell> = {
  SUCCESS: TrendingUp,
  WARNING: AlertTriangle,
  ERROR: Shield,
  INFO: Radio,
};

const SEVERITY_COLOR: Record<string, string> = {
  SUCCESS: "var(--color-profit)",
  WARNING: "var(--color-warning)",
  ERROR: "var(--color-loss)",
  INFO: "var(--color-accent)",
};

function formatTimeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// Filter to important events only (not every scan)
function isNotifiable(event: AgentEvent): boolean {
  const type = event.event_type || "";
  const agent = event.agent || "";
  // Include: trades, risk rejections, thesis checks, errors, trailing stops
  if (type === "ORDER" || type === "TRADE_CLOSE" || type === "POSITION_CLOSED_DETECTED") return true;
  if (type === "TRAILING_STOP") return true;
  if (type === "THESIS_CHECK") return true;
  if (type === "RISK_CHECK" && event.title?.includes("REJECTED")) return true;
  if (event.severity === "ERROR") return true;
  if (agent === "CLAUDE" && type === "SIGNAL" && !event.title?.includes("HOLD")) return true;
  return false;
}

export default function NotificationCenter() {
  const { events } = useAgentEvents();
  const [open, setOpen] = useState(false);
  const [seenCount, setSeenCount] = useState(0);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const notifications = events.filter(isNotifiable).slice(0, 20);
  const unreadCount = Math.max(0, notifications.length - seenCount);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  function handleOpen() {
    setOpen(!open);
    if (!open) setSeenCount(notifications.length);
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell button */}
      <button
        onClick={handleOpen}
        className="relative w-9 h-9 flex items-center justify-center rounded-lg transition-colors"
        style={{
          backgroundColor: open ? "var(--color-bg-elevated)" : "transparent",
          color: "var(--color-text-secondary)",
        }}
        aria-label="Notifications"
      >
        <Bell size={15} />
        {unreadCount > 0 && (
          <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold"
            style={{
              backgroundColor: "var(--color-loss)",
              color: "#fff",
            }}
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </motion.span>
        )}
      </button>

      {/* Dropdown */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-11 w-[360px] rounded-xl overflow-hidden z-50"
            style={{
              backgroundColor: "var(--color-bg-surface-solid)",
              border: "1px solid var(--color-border)",
              boxShadow: "var(--glass-shadow)",
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-4 py-2.5"
              style={{ borderBottom: "1px solid var(--color-border)" }}
            >
              <span className="text-xs font-semibold" style={{ color: "var(--color-text-primary)" }}>
                Notifications
              </span>
              <button
                onClick={() => setOpen(false)}
                className="w-6 h-6 flex items-center justify-center rounded"
                style={{ color: "var(--color-text-tertiary)" }}
              >
                <X size={14} />
              </button>
            </div>

            {/* List */}
            <div className="max-h-[400px] overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="py-10 text-center">
                  <Bell size={20} style={{ color: "var(--color-text-tertiary)", margin: "0 auto 8px", opacity: 0.4 }} />
                  <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
                    No notifications yet
                  </p>
                </div>
              ) : (
                notifications.map((event, idx) => {
                  const Icon = SEVERITY_ICON[event.severity] || Radio;
                  const color = SEVERITY_COLOR[event.severity] || "var(--color-accent)";
                  const isUnread = idx < unreadCount;

                  return (
                    <motion.div
                      key={event.id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.03 }}
                      className="flex items-start gap-3 px-4 py-3 transition-colors"
                      style={{
                        borderBottom: "1px solid var(--color-border)",
                        backgroundColor: isUnread ? `${color}08` : "transparent",
                      }}
                    >
                      <div
                        className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                        style={{ backgroundColor: `${color}15` }}
                      >
                        <Icon size={13} style={{ color }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[11px] leading-snug" style={{ color: "var(--color-text-primary)" }}>
                          {event.title}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          {event.pair && (
                            <span
                              className="text-[9px] font-mono px-1 py-0.5 rounded"
                              style={{ backgroundColor: "var(--color-bg-elevated)", color: "var(--color-text-tertiary)" }}
                            >
                              {event.pair.replace("_", "/")}
                            </span>
                          )}
                          <span className="text-[9px]" style={{ color: "var(--color-text-tertiary)" }}>
                            {formatTimeAgo(event.created_at)}
                          </span>
                        </div>
                      </div>
                      {isUnread && (
                        <span
                          className="w-1.5 h-1.5 rounded-full shrink-0 mt-2"
                          style={{ backgroundColor: color }}
                        />
                      )}
                    </motion.div>
                  );
                })
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
