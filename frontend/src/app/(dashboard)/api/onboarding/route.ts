import { NextRequest, NextResponse } from "next/server";
import { backendAuthHeaders } from "@/lib/backend-auth";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const backendUrl =
    process.env.BACKEND_URL ||
    "https://lumitrade-engine-production.up.railway.app";

  try {
    const body = await req.json();
    const { message, account_id } = body;

    if (!message) {
      return NextResponse.json(
        { error: "Missing 'message' field" },
        { status: 400 }
      );
    }

    const res = await fetch(`${backendUrl}/onboarding`, {
      method: "POST",
      headers: backendAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ message, account_id: account_id || "default" }),
    });

    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }

    return NextResponse.json(
      { response: "Onboarding service is starting up. Please try again.", completed: false },
      { status: 503 }
    );
  } catch {
    return NextResponse.json(
      { response: "Unable to reach onboarding service.", completed: false },
      { status: 500 }
    );
  }
}
