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
  "/journal": "Trade Journal",
  "/coach": "AI Coach",
  "/intelligence": "Intel Report",
  "/marketplace": "Marketplace",
  "/copy": "Copy Trading",
  "/backtest": "Backtest",
  "/api-keys": "API Access",
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
    <span className="font-mono text-[11px] tabular-nums" style={{ color: "var(--color-text-tertiary)" }}>
      {time}{" "}
      <span style={{ opacity: 0.5 }}>UTC</span>
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
        background: "rgba(8, 15, 26, 0.8)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderBottom: "1px solid rgba(30, 55, 92, 0.2)",
      }}
    >
      {/* Left: Page title */}
      <h1
        className="text-sm font-semibold tracking-tight"
        style={{
          fontFamily: "'Space Grotesk', sans-serif",
          color: "var(--color-text-primary)",
        }}
      >
        {getPageTitle(pathname)}
      </h1>

      {/* Right: controls */}
      <div className="flex items-center gap-3">
        {/* Trading mode badge */}
        <span
          className="text-[9px] font-bold tracking-widest px-2 py-0.5 rounded-full"
          style={mode === "LIVE" ? {
            background: "rgba(0, 200, 150, 0.1)",
            color: "var(--color-profit)",
          } : {
            background: "rgba(255, 179, 71, 0.1)",
            color: "var(--color-warning)",
          }}
        >
          {mode}
        </span>

        <NotificationCenter />
        <ThemeToggle />
        <StatusDot status={systemStatus} size="sm" />
        <UTCClock />
      </div>
    </header>
  );
}
