"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import StatusDot from "@/components/ui/StatusDot";
import ThemeToggle from "@/components/ui/ThemeToggle";
import NotificationCenter from "@/components/ui/NotificationCenter";
import { useSystemStatus } from "@/hooks/useSystemStatus";

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/signals": "Signals",
  "/trades": "Trade History",
  "/analytics": "Analytics",
  "/settings": "Settings",
};

function getPageTitle(pathname: string | null): string {
  if (!pathname) return "Lumitrade";
  for (const [prefix, title] of Object.entries(PAGE_TITLES)) {
    if (pathname.startsWith(prefix)) return title;
  }
  return "Lumitrade";
}

function UTCClock() {
  const [time, setTime] = useState<string>("");

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setTime(
        now.getUTCHours().toString().padStart(2, "0") +
          ":" +
          now.getUTCMinutes().toString().padStart(2, "0") +
          ":" +
          now.getUTCSeconds().toString().padStart(2, "0")
      );
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  if (!time) return null;

  return (
    <span className="text-micro" style={{ color: "var(--color-text-tertiary)" }}>
      {time}{" "}
      <span style={{ opacity: 0.6 }}>UTC</span>
    </span>
  );
}

export default function TopBar() {
  const pathname = usePathname();
  const { health } = useSystemStatus();

  const mode = health?.trading.mode ?? "PAPER";
  const systemStatus = health?.status ?? "offline";

  return (
    <header
      className="fixed top-0 right-0 left-0 lg:left-60 z-20 h-12 flex items-center justify-between px-5 pl-14 lg:pl-5"
      style={{
        background: "var(--color-bg-surface)",
        backdropFilter: "var(--glass-blur)",
        WebkitBackdropFilter: "var(--glass-blur)",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      {/* Left -- Page title */}
      <h1
        className="text-base font-bold tracking-tight"
        style={{ color: "var(--color-text-primary)" }}
      >
        {getPageTitle(pathname)}
      </h1>

      {/* Right -- mode badge, status, clock */}
      <div className="flex items-center gap-4">

        {/* Trading mode badge */}
        {mode === "LIVE" ? (
          <span className="text-[10px] font-label px-2 py-0.5 rounded bg-profit-dim text-profit">
            LIVE
          </span>
        ) : (
          <span className="text-[10px] font-label px-2 py-0.5 rounded bg-warning-dim text-warning">
            PAPER
          </span>
        )}

        {/* Notifications */}
        <NotificationCenter />

        {/* Theme toggle */}
        <ThemeToggle />

        {/* Connection status */}
        <StatusDot status={systemStatus} size="sm" />

        {/* UTC clock */}
        <UTCClock />
      </div>
    </header>
  );
}
