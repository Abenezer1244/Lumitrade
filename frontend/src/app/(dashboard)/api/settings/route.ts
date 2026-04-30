import { NextRequest, NextResponse } from "next/server";
import { backendAuthHeaders } from "@/lib/backend-auth";

export const dynamic = "force-dynamic";

const DEFAULTS = {
  riskPct: 0.5,
  maxPositions: 5,
  maxPerPair: 5,
  confidence: 70,
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
      headers: backendAuthHeaders({ "Content-Type": "application/json" }),
      cache: "no-store",
    });

    if (res.status === 401) {
      return NextResponse.json(
        { error: "Engine auth failed — INTERNAL_API_SECRET mismatch. Redeploy both services." },
        { status: 503 }
      );
    }

    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }

    return NextResponse.json(
      { error: `Engine returned ${res.status}` },
      { status: 502 }
    );
  } catch {
    // Backend unreachable — return defaults so UI doesn't hard-crash
    return NextResponse.json(DEFAULTS);
  }
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const backendUrl =
    process.env.BACKEND_URL ||
    "http://lumitrade-engine.railway.internal:8000";

  try {
    const res = await fetch(`${backendUrl}/settings`, {
      method: "POST",
      headers: backendAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });

    if (res.status === 401) {
      return NextResponse.json(
        { error: "Engine auth failed — settings not saved. INTERNAL_API_SECRET mismatch." },
        { status: 503 }
      );
    }

    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }

    return NextResponse.json(
      { error: `Engine returned ${res.status}` },
      { status: 502 }
    );
  } catch {
    return NextResponse.json(
      { error: "Engine unreachable — settings not saved" },
      { status: 503 }
    );
  }
}
