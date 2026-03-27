import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;

  if (!url || !key) return NextResponse.json({ trades: [] });

  try {
    const res = await fetch(
      `${url}/rest/v1/trades?select=confidence_score,outcome,pnl_usd&status=eq.CLOSED`,
      {
        headers: { apikey: key, Authorization: `Bearer ${key}` },
        cache: "no-store",
      }
    );
    if (!res.ok) return NextResponse.json({ trades: [] });
    const trades = await res.json();
    return NextResponse.json({ trades });
  } catch {
    return NextResponse.json({ trades: [] });
  }
}
