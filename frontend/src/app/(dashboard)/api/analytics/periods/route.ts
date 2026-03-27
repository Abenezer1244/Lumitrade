import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

interface Trade {
  pnl_usd: string | null;
  outcome: string | null;
  closed_at: string | null;
}

function computeStats(trades: Trade[]) {
  const pnl = trades.reduce((s, t) => s + (parseFloat(t.pnl_usd || "0") || 0), 0);
  const wins = trades.filter((t) => t.outcome === "WIN").length;
  return {
    pnl: Math.round(pnl * 100) / 100,
    trades: trades.length,
    wins,
    winRate: trades.length > 0 ? (wins / trades.length) * 100 : 0,
  };
}

export async function GET() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;

  const empty = { pnl: 0, trades: 0, wins: 0, winRate: 0 };

  if (!url || !key) {
    return NextResponse.json({
      Today: empty,
      "This Week": empty,
      "This Month": empty,
      "All Time": empty,
    });
  }

  try {
    const headers = { apikey: key, Authorization: `Bearer ${key}` };
    const res = await fetch(
      `${url}/rest/v1/trades?select=pnl_usd,outcome,closed_at&status=eq.CLOSED&order=closed_at.desc`,
      { headers, cache: "no-store" }
    );
    if (!res.ok) {
      return NextResponse.json({ Today: empty, "This Week": empty, "This Month": empty, "All Time": empty });
    }
    const trades: Trade[] = await res.json();

    const now = new Date();

    // Today
    const todayStart = new Date(now);
    todayStart.setUTCHours(0, 0, 0, 0);
    const todayTrades = trades.filter((t) => t.closed_at && new Date(t.closed_at) >= todayStart);

    // This Week (Monday start)
    const weekStart = new Date(now);
    const day = weekStart.getUTCDay();
    const diff = day === 0 ? 6 : day - 1; // Monday = 0
    weekStart.setUTCDate(weekStart.getUTCDate() - diff);
    weekStart.setUTCHours(0, 0, 0, 0);
    const weekTrades = trades.filter((t) => t.closed_at && new Date(t.closed_at) >= weekStart);

    // This Month
    const monthStart = new Date(now.getUTCFullYear(), now.getUTCMonth(), 1);
    const monthTrades = trades.filter((t) => t.closed_at && new Date(t.closed_at) >= monthStart);

    return NextResponse.json({
      Today: computeStats(todayTrades),
      "This Week": computeStats(weekTrades),
      "This Month": computeStats(monthTrades),
      "All Time": computeStats(trades),
    });
  } catch {
    return NextResponse.json({ Today: empty, "This Week": empty, "This Month": empty, "All Time": empty });
  }
}
