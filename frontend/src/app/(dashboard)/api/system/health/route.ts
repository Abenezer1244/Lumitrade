import { NextResponse } from "next/server";

const FALLBACK = {
  status: "degraded" as const,
  instance_id: "unknown",
  is_primary: true,
  timestamp: new Date().toISOString(),
  uptime_seconds: 0,
  components: {
    oanda_api: { status: "offline", latency_ms: 0 },
    ai_brain: { status: "offline", last_call_ago_s: 0 },
    database: { status: "offline", latency_ms: 0 },
    price_feed: { status: "offline", last_tick_ago_s: 0 },
    risk_engine: { status: "ok", state: "NORMAL" },
    circuit_breaker: { status: "closed" },
  },
  trading: {
    mode: "PAPER",
    open_positions: 0,
    daily_pnl_usd: 0,
    signals_today: 0,
  },
};

function transformBackendHealth(data: Record<string, unknown>) {
  // Backend returns flat component statuses like "ok"/"error"
  // Frontend expects objects like { status: "ok", latency_ms: 0 }
  const comps = (data.components || {}) as Record<string, unknown>;
  const trading = (data.trading || {}) as Record<string, unknown>;

  return {
    status: data.status || "degraded",
    instance_id: data.instance_id || "unknown",
    is_primary: true,
    timestamp: data.timestamp || new Date().toISOString(),
    uptime_seconds: data.uptime_seconds || 0,
    components: {
      oanda_api: {
        status: typeof comps.oanda === "string" ? comps.oanda : "offline",
        latency_ms: 0,
      },
      ai_brain: {
        status: typeof comps.state === "string" && comps.state === "ok" ? "ok" : "offline",
        last_call_ago_s: 0,
      },
      database: {
        status: typeof comps.database === "string" ? comps.database : "offline",
        latency_ms: 0,
      },
      price_feed: {
        status: typeof comps.state === "string" && comps.state === "ok" ? "ok" : "offline",
        last_tick_ago_s: 0,
      },
      risk_engine: {
        status: typeof comps.state === "string" && comps.state !== "error" ? "ok" : "offline",
        state: (trading.risk_state as string) || "NORMAL",
      },
      circuit_breaker: {
        status: typeof comps.lock === "string" ? comps.lock : "closed",
      },
    },
    trading: {
      mode: (trading.mode as string) || "PAPER",
      open_positions: (trading.open_trades as number) || 0,
      daily_pnl_usd: (trading.daily_pnl_usd as number) || 0,
      signals_today: (trading.signals_today as number) || 0,
    },
  };
}

export async function GET() {
  try {
    const backendUrl =
      process.env.BACKEND_URL ||
      "https://lumitrade-engine-production.up.railway.app";
    const res = await fetch(`${backendUrl}/health`, {
      next: { revalidate: 10 },
      signal: AbortSignal.timeout(5000),
    });
    const raw = await res.json();
    return NextResponse.json(transformBackendHealth(raw));
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
