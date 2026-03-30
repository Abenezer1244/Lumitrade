import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const pair = searchParams.get("pair") || "EUR_USD";
  const granularity = searchParams.get("granularity") || "H1";
  const count = searchParams.get("count") || "100";

  const backendUrl =
    process.env.BACKEND_URL ||
    "http://lumitrade-engine.railway.internal:8000";

  try {
    const res = await fetch(
      `${backendUrl}/candles?pair=${pair}&granularity=${granularity}&count=${count}`,
      { cache: "no-store" }
    );

    if (!res.ok) {
      return NextResponse.json({ candles: [] });
    }

    const data = await res.json();
    return NextResponse.json({ candles: data.candles || [] });
  } catch {
    return NextResponse.json({ candles: [] });
  }
}
