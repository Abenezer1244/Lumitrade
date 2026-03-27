import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const PIP_SIZE: Record<string, number> = {
  EUR_USD: 0.0001,
  GBP_USD: 0.0001,
  USD_JPY: 0.01,
  USD_CHF: 0.0001,
  AUD_USD: 0.0001,
  USD_CAD: 0.0001,
  NZD_USD: 0.0001,
  EUR_JPY: 0.01,
  GBP_JPY: 0.01,
};

function pipValue(pair: string, rate: number): number {
  const ps = PIP_SIZE[pair] ?? 0.0001;
  if (pair.endsWith("_USD")) return ps;
  if (pair.startsWith("USD_") && rate > 0) return ps / rate;
  return ps;
}

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
    const res = await fetch(
      `${url}/rest/v1/trades?select=*&status=eq.OPEN&order=opened_at.desc`,
      {
        headers: { apikey: key, Authorization: `Bearer ${key}` },
        cache: "no-store",
      }
    );
    if (!res.ok) return NextResponse.json({ positions: [] });
    const data = await res.json();

    if (!data || data.length === 0) {
      return NextResponse.json({ positions: [] });
    }

    // Collect unique pairs from open trades
    const pairs = Array.from(new Set((data as Record<string, unknown>[]).map((t) => t.pair as string)));

    // Fetch live prices from backend
    const backendUrl =
      process.env.BACKEND_URL ||
      "http://lumitrade-engine.railway.internal:8000";
    let prices: Record<string, { bid: number; ask: number; mid: number }> = {};
    try {
      const priceRes = await fetch(
        `${backendUrl}/prices?pairs=${pairs.join(",")}`,
        { cache: "no-store" }
      );
      if (priceRes.ok) {
        const priceData = await priceRes.json();
        prices = priceData.prices || {};
      }
    } catch {
      // If pricing fails, we'll return 0 P&L
    }

    const positions = (data as Record<string, unknown>[]).map((trade) => {
      const pair = trade.pair as string;
      const entry = Number(trade.entry_price) || 0;
      const direction = trade.direction as string;
      const units = Number(trade.position_size) || 0;
      const priceInfo = prices[pair];

      if (!priceInfo || !entry) {
        return { ...trade, live_pnl_pips: 0, live_pnl_usd: 0, current_price: entry };
      }

      const currentPrice = priceInfo.mid;
      const ps = PIP_SIZE[pair] ?? 0.0001;
      const priceDiff = direction === "BUY"
        ? currentPrice - entry
        : entry - currentPrice;
      const pnlPips = Math.round((priceDiff / ps) * 10) / 10;
      const pv = pipValue(pair, currentPrice);
      const pnlUsd = Math.round(pnlPips * units * pv * 100) / 100;

      return {
        ...trade,
        live_pnl_pips: pnlPips,
        live_pnl_usd: pnlUsd,
        current_price: currentPrice,
      };
    });

    return NextResponse.json({ positions });
  } catch {
    return NextResponse.json({ positions: [] });
  }
}
