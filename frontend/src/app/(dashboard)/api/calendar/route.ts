import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const backendUrl =
    process.env.BACKEND_URL ||
    "http://lumitrade-engine.railway.internal:8000";

  try {
    const res = await fetch(`${backendUrl}/calendar?period=604800`, {
      cache: "no-store",
    });
    if (!res.ok) return NextResponse.json({ events: [] });
    const data = await res.json();
    return NextResponse.json({ events: data.events || [] });
  } catch {
    return NextResponse.json({ events: [] });
  }
}
