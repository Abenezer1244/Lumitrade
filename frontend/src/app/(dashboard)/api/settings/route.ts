import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const DEFAULTS = {
  riskPct: 1.0,
  maxPositions: 3,
  maxPerPair: 1,
  confidence: 65,
  mode: "PAPER" as const,
  guardrails: {
    maxPositionUnits: 500_000,
    dailyLossLimitPct: 5.0,
    weeklyLossLimitPct: 10.0,
  },
};

export async function GET() {
  const backendUrl =
    process.env.BACKEND_URL ||
    "http://lumitrade-engine.railway.internal:8000";

  try {
    const res = await fetch(`${backendUrl}/settings`, {
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Backend unavailable, fall through to defaults
  }

  return NextResponse.json(DEFAULTS);
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const backendUrl =
    process.env.BACKEND_URL ||
    "http://lumitrade-engine.railway.internal:8000";

  try {
    const res = await fetch(`${backendUrl}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Backend unavailable
  }

  return NextResponse.json(body);
}
