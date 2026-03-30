import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;

  if (!url || !key) {
    return NextResponse.json(
      { error: "Server misconfigured: missing SUPABASE_URL or SERVICE_KEY" },
      { status: 500 }
    );
  }

  try {
    const headers = { apikey: key, Authorization: `Bearer ${key}` };

    // Fetch trades and count in parallel
    const [tradesRes, countRes] = await Promise.all([
      fetch(
        `${url}/rest/v1/trades?select=*&order=opened_at.desc&limit=100`,
        { headers, cache: "no-store" }
      ),
      fetch(
        `${url}/rest/v1/trades?select=id&status=eq.CLOSED`,
        { headers: { ...headers, Prefer: "count=exact" }, cache: "no-store" }
      ),
    ]);

    if (!tradesRes.ok) return NextResponse.json({ trades: [], total: 0 });
    const trades = (await tradesRes.json()) || [];

    // Extract total from content-range header (Supabase returns "0-N/total")
    const contentRange = countRes.headers.get("content-range");
    const total = contentRange
      ? parseInt(contentRange.split("/").pop() || "0", 10)
      : trades.length;

    return NextResponse.json({ trades, total });
  } catch {
    return NextResponse.json({ trades: [] });
  }
}
