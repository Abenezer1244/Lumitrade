import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const pairs = searchParams.get("pairs") || "EUR_USD,GBP_USD,USD_JPY";

  const backendUrl =
    process.env.BACKEND_URL ||
    "https://lumitrade-engine-production.up.railway.app";

  try {
    const res = await fetch(`${backendUrl}/prices?pairs=${pairs}`, {
      signal: AbortSignal.timeout(5000),
      cache: "no-store",
    });
    if (!res.ok) return NextResponse.json({ prices: {} });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ prices: {} });
  }
}
