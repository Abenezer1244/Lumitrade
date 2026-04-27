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
    circuit_breaker: { status: "CLOSED" },
  },
  trading: {
    mode: "PAPER",
    open_positions: 0,
    daily_pnl_usd: 0,
    signals_today: 0,
  },
};

function transformBackendHealth(data: Record<string, unknown>, latencyMs = 0) {
  // Backend may return flat strings (old) or structured objects (new)
  const comps = (data.components || {}) as Record<string, unknown>;
  const trading = (data.trading || {}) as Record<string, unknown>;

  // Detect if backend returns structured objects or flat strings
  const isStructured = typeof comps.database === "object";

  // Helper for structured format
  const getObj = (key: string) =>
    isStructured ? (comps[key] as Record<string, unknown>) || {} : {};

  // Helper for flat format
  const getFlat = (key: string) =>
    typeof comps[key] === "string" ? (comps[key] as string) : null;

  // Calculate last signal ago from trading.last_signal_at
  let lastSignalAgo = 0;
  const lastSignalAt = trading.last_signal_at;
  if (lastSignalAt && typeof lastSignalAt === "object") {
    const times = Object.values(lastSignalAt as Record<string, string>).filter(Boolean);
    if (times.length > 0) {
      const mostRecent = Math.max(...times.map((t) => new Date(t).getTime()));
      if (mostRecent > 0) {
        lastSignalAgo = Math.round((Date.now() - mostRecent) / 1000);
      }
    }
  }

  // Use measured latency for OANDA and DB
  const dbLatency = isStructured
    ? (getObj("database").latency_ms as number) || latencyMs
    : latencyMs;

  return {
    status: data.status || "degraded",
    instance_id: data.instance_id || "unknown",
    is_primary: true,
    timestamp: data.timestamp || new Date().toISOString(),
    uptime_seconds: data.uptime_seconds || 0,
    components: {
      oanda_api: {
        status: isStructured
          ? (getObj("oanda").status as string) || "offline"
          : getFlat("oanda") || "offline",
        latency_ms: dbLatency,
      },
      ai_brain: {
        status: isStructured
          ? (getObj("ai_brain").status as string) || (lastSignalAgo < 1200 ? "ok" : "offline")
          : lastSignalAgo > 0 && lastSignalAgo < 1200 ? "ok" : "offline",
        last_call_ago_s: isStructured
          ? (getObj("ai_brain").last_call_ago_s as number) || lastSignalAgo
          : lastSignalAgo,
      },
      database: {
        status: isStructured
          ? (getObj("database").status as string) || "offline"
          : getFlat("database") || "offline",
        latency_ms: dbLatency,
      },
      price_feed: {
        status: isStructured
          ? (getObj("price_feed").status as string) || "offline"
          : getFlat("state") === "ok" ? "ok" : "offline",
        last_tick_ago_s: isStructured
          ? (getObj("price_feed").last_tick_ago_s as number) || 0
          : 0,
      },
      risk_engine: {
        status: isStructured
          ? (getObj("risk_engine").status as string) || "ok"
          : getFlat("state") ? "ok" : "offline",
        state: isStructured
          ? (getObj("risk_engine").state as string) || "NORMAL"
          : (trading.risk_state as string) || "NORMAL",
      },
      circuit_breaker: {
        status: isStructured
          ? (getObj("circuit_breaker").status as string) || "CLOSED"
          : "CLOSED",
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

    const startTime = Date.now();
    const res = await fetch(`${backendUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    const latencyMs = Date.now() - startTime;
    const raw = await res.json();

    // If backend returns structured components (new format), pass through directly
    const comps = raw.components || {};
    const trading = raw.trading || {};
    const dbComp = comps.database;

    if (dbComp && typeof dbComp === "object" && dbComp.status) {
      // New structured format — pass through with frontend key mapping
      return NextResponse.json({
        status: raw.status || "degraded",
        instance_id: raw.instance_id || "unknown",
        is_primary: true,
        timestamp: raw.timestamp || new Date().toISOString(),
        uptime_seconds: raw.uptime_seconds || 0,
        components: {
          oanda_api: comps.oanda || { status: "offline", latency_ms: 0 },
          ai_brain: comps.ai_brain || { status: "offline", last_call_ago_s: 0 },
          database: comps.database || { status: "offline", latency_ms: 0 },
          price_feed: comps.price_feed || { status: "offline", last_tick_ago_s: 0 },
          risk_engine: comps.risk_engine || { status: "ok", state: "NORMAL" },
          circuit_breaker: comps.circuit_breaker || { status: "CLOSED" },
        },
        trading: {
          mode: trading.mode || "PAPER",
          open_positions: trading.open_trades || 0,
          daily_pnl_usd: trading.daily_pnl_usd || 0,
          signals_today: trading.signals_today || 0,
        },
      });
    }

    // Old flat format fallback
    return NextResponse.json(transformBackendHealth(raw, latencyMs));
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
