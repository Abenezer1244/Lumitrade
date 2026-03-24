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
  // Backend now returns structured component objects with real metrics
  const comps = (data.components || {}) as Record<string, Record<string, unknown>>;
  const trading = (data.trading || {}) as Record<string, unknown>;

  // Helper to safely read component data
  const getComp = (key: string) => comps[key] || {};

  return {
    status: data.status || "degraded",
    instance_id: data.instance_id || "unknown",
    is_primary: true,
    timestamp: data.timestamp || new Date().toISOString(),
    uptime_seconds: data.uptime_seconds || 0,
    components: {
      oanda_api: {
        status: (getComp("oanda").status as string) || "offline",
        latency_ms: (getComp("oanda").latency_ms as number) || 0,
      },
      ai_brain: {
        status: (getComp("ai_brain").status as string) || "offline",
        last_call_ago_s: (getComp("ai_brain").last_call_ago_s as number) || 0,
      },
      database: {
        status: (getComp("database").status as string) || "offline",
        latency_ms: (getComp("database").latency_ms as number) || 0,
      },
      price_feed: {
        status: (getComp("price_feed").status as string) || "offline",
        last_tick_ago_s: (getComp("price_feed").last_tick_ago_s as number) || 0,
      },
      risk_engine: {
        status: (getComp("risk_engine").status as string) || "offline",
        state: (getComp("risk_engine").state as string) || "NORMAL",
      },
      circuit_breaker: {
        status: (getComp("circuit_breaker").status as string) || "CLOSED",
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
