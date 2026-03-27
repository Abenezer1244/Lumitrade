import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const pair = searchParams.get("pair") || "EUR_USD";
  const granularity = searchParams.get("granularity") || "H1";
  const count = searchParams.get("count") || "100";

  const oandaKey = process.env.OANDA_API_KEY_DATA;
  const oandaAccount = process.env.OANDA_ACCOUNT_ID;
  const oandaEnv = process.env.OANDA_ENVIRONMENT || "practice";

  if (!oandaKey || !oandaAccount) {
    return NextResponse.json({ candles: [] });
  }

  const baseUrl = oandaEnv === "live"
    ? "https://api-fxtrade.oanda.com"
    : "https://api-fxpractice.oanda.com";

  try {
    const res = await fetch(
      `${baseUrl}/v3/instruments/${pair}/candles?granularity=${granularity}&count=${count}&price=BA`,
      {
        headers: { Authorization: `Bearer ${oandaKey}` },
        cache: "no-store",
      }
    );

    if (!res.ok) {
      return NextResponse.json({ candles: [] });
    }

    const data = await res.json();
    const candles = (data.candles || [])
      .filter((c: Record<string, unknown>) => (c as { complete: boolean }).complete !== false)
      .map((c: Record<string, unknown>) => {
        const mid = c.mid as Record<string, string> | undefined;
        const bid = c.bid as Record<string, string> | undefined;
        const ask = c.ask as Record<string, string> | undefined;
        const source = mid || bid || { o: "0", h: "0", l: "0", c: "0" };
        return {
          time: Math.floor(new Date(c.time as string).getTime() / 1000),
          open: parseFloat(source.o),
          high: parseFloat(source.h),
          low: parseFloat(source.l),
          close: parseFloat(source.c),
          volume: c.volume || 0,
          spread: bid && ask
            ? parseFloat(ask.c) - parseFloat(bid.c)
            : 0,
        };
      });

    return NextResponse.json({ candles });
  } catch {
    return NextResponse.json({ candles: [] });
  }
}
