"use client";

import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Newspaper } from "lucide-react";

interface CalendarEvent {
  title: string;
  currency: string;
  impact: number;
  forecast: string | null;
  actual: string | null;
  previous: string | null;
  market: string | null;
  timestamp: number;
  region: string;
  unit: string;
}

const IMPACT_LABEL: Record<number, { text: string; color: string; bg: string }> = {
  1: { text: "LOW", color: "var(--color-text-tertiary)", bg: "var(--color-bg-elevated)" },
  2: { text: "MED", color: "var(--color-warning)", bg: "var(--color-warning-dim)" },
  3: { text: "HIGH", color: "var(--color-loss)", bg: "var(--color-loss-dim)" },
};

function formatEventTime(timestamp: number): string {
  const d = new Date(timestamp * 1000);
  const now = new Date();
  const diff = timestamp * 1000 - now.getTime();

  if (diff > 0 && diff < 86400000) {
    const hours = Math.floor(diff / 3600000);
    const mins = Math.floor((diff % 3600000) / 60000);
    return hours > 0 ? `in ${hours}h ${mins}m` : `in ${mins}m`;
  }

  const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  return `${dayNames[d.getUTCDay()]} ${d.getUTCHours().toString().padStart(2, "0")}:${d.getUTCMinutes().toString().padStart(2, "0")}`;
}

export default function NewsFeed() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function fetchCalendar() {
      try {
        const res = await fetch("/api/calendar");
        if (!res.ok) return;
        const data = await res.json();
        setEvents(data.events || []);
      } catch { /* silent */ }
      finally { setLoading(false); }
    }

    fetchCalendar();
    const timer = setInterval(fetchCalendar, 300_000); // Refresh every 5 min
    return () => clearInterval(timer);
  }, []);

  // Filter to upcoming and recent events (past 24h + next 7 days)
  const now = Math.floor(Date.now() / 1000);
  const relevant = events.filter(
    (e) => e.timestamp > now - 86400 && e.impact >= 2
  );

  if (loading) {
    return (
      <div className="glass p-4 animate-pulse h-[120px]" />
    );
  }

  return (
    <div className="glass p-4 overflow-hidden flex-1 flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div
          className="w-6 h-6 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: "var(--color-accent-glow)" }}
        >
          <Newspaper size={12} style={{ color: "var(--color-accent)" }} aria-hidden="true" />
        </div>
        <span className="text-sm font-semibold" style={{ color: "var(--color-text-primary)", fontFamily: "'Space Grotesk', sans-serif" }}>
          Economic Calendar
        </span>
        <span
          className="text-[10px] font-mono px-1.5 py-0.5 rounded-full"
          style={{ background: "var(--color-bg-elevated)", color: "var(--color-text-tertiary)" }}
        >
          {relevant.length}
        </span>
      </div>

      {/* Event list */}
      {relevant.length === 0 ? (
        <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
          No major events this week.
        </p>
      ) : (
        <div
          ref={scrollRef}
          className="space-y-1.5 flex-1 overflow-y-auto pr-1"
          style={{ scrollbarWidth: "thin" }}
        >
          <AnimatePresence>
            {relevant.slice(0, 5).map((event, i) => {
              const impact = IMPACT_LABEL[event.impact] || IMPACT_LABEL[1];
              const isPast = event.timestamp < now;
              const beat = event.actual && event.forecast
                ? parseFloat(event.actual) > parseFloat(event.forecast)
                : null;

              return (
                <motion.div
                  key={`${event.title}-${event.timestamp}`}
                  className="flex items-center gap-2 text-[11px]"
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                >
                  {/* Impact badge */}
                  <span
                    className="shrink-0 text-[8px] font-bold px-1.5 py-0.5 rounded"
                    style={{ color: impact.color, backgroundColor: impact.bg }}
                  >
                    {impact.text}
                  </span>

                  {/* Currency */}
                  <span className="shrink-0 font-mono font-bold" style={{ color: "var(--color-text-primary)", width: 28 }}>
                    {event.currency}
                  </span>

                  {/* Title */}
                  <span className="truncate flex-1" style={{ color: isPast ? "var(--color-text-tertiary)" : "var(--color-text-secondary)" }}>
                    {event.title}
                  </span>

                  {/* Actual vs forecast */}
                  {isPast && event.actual ? (
                    <span
                      className="shrink-0 font-mono text-[10px]"
                      style={{ color: beat === true ? "var(--color-profit)" : beat === false ? "var(--color-loss)" : "var(--color-text-tertiary)" }}
                    >
                      {event.actual}
                    </span>
                  ) : (
                    <span className="shrink-0 font-mono text-[10px]" style={{ color: "var(--color-text-tertiary)" }}>
                      {formatEventTime(event.timestamp)}
                    </span>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
