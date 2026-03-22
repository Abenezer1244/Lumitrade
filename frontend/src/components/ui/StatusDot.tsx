"use client";
interface Props { status: string; size?: "sm" | "md"; showLabel?: boolean }
export default function StatusDot({ status, size = "sm", showLabel }: Props) {
  const sizeClass = size === "md" ? "w-3 h-3" : "w-2 h-2";
  const colorMap: Record<string, string> = {
    ok: "bg-profit", healthy: "bg-profit", online: "bg-profit",
    degraded: "bg-warning animate-pulse", warning: "bg-warning animate-pulse",
    offline: "bg-loss", error: "bg-loss",
    closed: "bg-profit", open: "bg-loss", half_open: "bg-warning",
  };
  const color = colorMap[status] || "bg-tertiary";
  const label = status === "ok" || status === "healthy" ? "Online" : status === "degraded" ? "Degraded" : status === "offline" ? "Offline" : status;
  return (
    <div className="flex items-center gap-1.5">
      <span className={`${sizeClass} rounded-full ${color}`} />
      {showLabel && <span className="text-xs text-secondary capitalize">{label}</span>}
    </div>
  );
}
