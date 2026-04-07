import { NextResponse } from "next/server";
import { backendAuthHeaders } from "@/lib/backend-auth";

export const dynamic = "force-dynamic";

const PIP_SIZE: Record<string, number> = {
  EUR_USD: 0.0001,
  GBP_USD: 0.0001,
  USD_JPY: 0.01,
  USD_CHF: 0.0001,
  AUD_USD: 0.0001,
  USD_CAD: 0.0001,
  NZD_USD: 0.0001,
  XAU_USD: 0.01,
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

    const backendUrl =
      process.env.BACKEND_URL ||
      "http://lumitrade-engine.railway.internal:8000";

    const pairs = Array.from(new Set((data as Record<string, unknown>[]).map((t) => t.pair as string)));
    let prices: Record<string, { bid: number; ask: number; mid: number }> = {};
    // Map broker_trade_id → OANDA's per-trade unrealized P&L
    let oandaPnlMap: Record<string, number> = {};

    try {
      const [priceRes, oandaTradesRes] = await Promise.all([
        fetch(`${backendUrl}/prices?pairs=${pairs.join(",")}`, { cache: "no-store" }),
        fetch(`${backendUrl}/oanda-trades`, { headers: backendAuthHeaders(), cache: "no-store" }),
      ]);
      if (priceRes.ok) {
        prices = (await priceRes.json()).prices || {};
      }
      if (oandaTradesRes.ok) {
        const oandaTrades = await oandaTradesRes.json();
        for (const t of (oandaTrades.trades || [])) {
          oandaPnlMap[t.id] = parseFloat(t.unrealizedPL || "0");
        }
      }
    } catch { /* continue with fallback */ }

    const openCount = (data as unknown[]).length;

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

      // Use OANDA's per-trade unrealizedPL when available (most accurate)
      // Falls back to pip math calculation if OANDA data unavailable
      const brokerId = trade.broker_trade_id as string;
      let pnlUsd: number;
      if (brokerId && oandaPnlMap[brokerId] !== undefined) {
        pnlUsd = Math.round(oandaPnlMap[brokerId] * 100) / 100;
      } else {
        const pv = pipValue(pair, currentPrice);
        pnlUsd = Math.round(pnlPips * units * pv * 100) / 100;
      }

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
