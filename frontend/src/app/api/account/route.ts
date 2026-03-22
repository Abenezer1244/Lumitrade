import { NextResponse } from "next/server";
export async function GET() {
  return NextResponse.json({
    balance: "0.00", equity: "0.00", margin_used: "0.00", margin_available: "0.00",
    open_trade_count: 0, daily_pnl_usd: "0.00", daily_pnl_pct: "0.00",
    daily_trade_count: 0, daily_win_count: 0, daily_win_rate: "0.00", mode: "PAPER",
  });
}
