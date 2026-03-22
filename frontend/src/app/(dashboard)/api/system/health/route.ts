import { NextResponse } from "next/server";
export async function GET() {
  return NextResponse.json({
    status: "healthy", instance_id: "cloud-primary", is_primary: true,
    timestamp: new Date().toISOString(), uptime_seconds: 0,
    components: {
      oanda_api: { status: "ok", latency_ms: 0 }, ai_brain: { status: "ok", last_call_ago_s: 0 },
      database: { status: "ok", latency_ms: 0 }, price_feed: { status: "ok", last_tick_ago_s: 0 },
      risk_engine: { status: "ok", state: "NORMAL" }, circuit_breaker: { status: "closed" },
    },
    trading: { mode: "PAPER", open_positions: 0, daily_pnl_usd: 0, signals_today: 0 },
  });
}
