"use client";
import { useSystemStatus } from "@/hooks/useSystemStatus";
import StatusDot from "@/components/ui/StatusDot";

interface ComponentInfo {
  label: string;
  status: string;
  detail: string;
}

export default function SystemStatusPanel() {
  const { health, loading } = useSystemStatus();

  if (loading || !health) {
    return <div className="bg-surface border border-border rounded-lg p-5 animate-pulse h-48" />;
  }

  const components: ComponentInfo[] = [
    {
      label: "OANDA API",
      status: health.components.oanda_api.status,
      detail: `${health.components.oanda_api.latency_ms}ms`,
    },
    {
      label: "AI Brain",
      status: health.components.ai_brain.status,
      detail: `${health.components.ai_brain.last_call_ago_s}s ago`,
    },
    {
      label: "Database",
      status: health.components.database.status,
      detail: `${health.components.database.latency_ms}ms`,
    },
    {
      label: "Price Feed",
      status: health.components.price_feed.status,
      detail: `${health.components.price_feed.last_tick_ago_s}s ago`,
    },
    {
      label: "Risk Engine",
      status: health.components.risk_engine.status,
      detail: health.components.risk_engine.state,
    },
    {
      label: "Circuit Breaker",
      status: health.components.circuit_breaker.status,
      detail: health.components.circuit_breaker.status.toUpperCase(),
    },
  ];

  const overallStatusColor =
    health.status === "healthy" ? "text-profit" :
    health.status === "degraded" ? "text-warning" : "text-loss";

  return (
    <div className="bg-surface border border-border rounded-lg p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-label text-tertiary">System Status</p>
        <span className={`text-xs font-bold uppercase ${overallStatusColor}`}>{health.status}</span>
      </div>
      <div className="space-y-2.5">
        {components.map(({ label, status, detail }) => (
          <div key={label} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <StatusDot status={status} size="sm" />
              <span className="text-xs text-primary">{label}</span>
            </div>
            <span className="text-[10px] font-mono text-tertiary">{detail}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 pt-3 border-t border-border flex items-center justify-between">
        <span className="text-[10px] text-tertiary">Uptime</span>
        <span className="text-[10px] font-mono text-secondary">
          {Math.floor(health.uptime_seconds / 3600)}h {Math.floor((health.uptime_seconds % 3600) / 60)}m
        </span>
      </div>
    </div>
  );
}
