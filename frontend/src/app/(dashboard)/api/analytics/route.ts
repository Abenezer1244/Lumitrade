import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const EMPTY_ANALYTICS = {
  total_trades: 0,
  win_rate: 0,
  profit_factor: 0,
  avg_win_pips: 0,
  avg_loss_pips: 0,
  largest_win_usd: 0,
  largest_loss_usd: 0,
  max_drawdown_pct: 0,
  sharpe_ratio: 0,
  expectancy_per_trade_usd: 0,
  equity_curve: [],
};

interface Trade {
  pnl_usd: string | null;
  pnl_pips: string | null;
  outcome: string | null;
  closed_at: string | null;
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
      `${url}/rest/v1/trades?select=pnl_usd,pnl_pips,outcome,closed_at&status=eq.CLOSED&order=closed_at.asc`,
      {
        headers: { apikey: key, Authorization: `Bearer ${key}` },
        cache: "no-store",
      }
    );
    if (!res.ok) return NextResponse.json(EMPTY_ANALYTICS);
    const trades: Trade[] = await res.json();

    if (!trades || trades.length === 0) {
      return NextResponse.json(EMPTY_ANALYTICS);
    }

    // Fetch real starting balance from OANDA via system_state
    let startingBalance = 100000;
    try {
      const balRes = await fetch(
        `${url}/rest/v1/system_state?id=eq.singleton&select=daily_opening_balance`,
        { headers: { apikey: key, Authorization: `Bearer ${key}` }, cache: "no-store" }
      );
      if (balRes.ok) {
        const rows = await balRes.json();
        if (rows?.[0]?.daily_opening_balance) {
          startingBalance = parseFloat(rows[0].daily_opening_balance) || 100000;
        }
      }
    } catch { /* use default */ }

    const wins = trades.filter((t) => t.outcome === "WIN");
    const losses = trades.filter((t) => t.outcome === "LOSS");

    const parsePnl = (t: Trade) => parseFloat(t.pnl_usd || "0") || 0;
    const parsePips = (t: Trade) => parseFloat(t.pnl_pips || "0") || 0;

    const totalPnl = trades.reduce((s, t) => s + parsePnl(t), 0);
    const totalWinPnl = wins.reduce((s, t) => s + parsePnl(t), 0);
    const totalLossPnl = Math.abs(
      losses.reduce((s, t) => s + parsePnl(t), 0)
    );

    // Equity curve
    let equity = startingBalance;
    const equityCurve = trades.map((t) => {
      equity += parsePnl(t);
      return { date: t.closed_at, equity: Math.round(equity * 100) / 100 };
    });

    // Max drawdown
    let peak = startingBalance;
    let maxDrawdownPct = 0;
    let runningEquity = startingBalance;
    for (const t of trades) {
      runningEquity += parsePnl(t);
      if (runningEquity > peak) peak = runningEquity;
      const drawdown = ((peak - runningEquity) / peak) * 100;
      if (drawdown > maxDrawdownPct) maxDrawdownPct = drawdown;
    }

    // Sharpe ratio (simplified — annualized daily returns)
    const returns = trades.map((t) => parsePnl(t));
    const meanReturn = totalPnl / trades.length;
    const variance =
      returns.reduce((s, r) => s + (r - meanReturn) ** 2, 0) / trades.length;
    const stdDev = Math.sqrt(variance);
    const sharpe = stdDev > 0 ? (meanReturn / stdDev) * Math.sqrt(252) : 0;

    return NextResponse.json({
      total_trades: trades.length,
      win_rate: (wins.length / trades.length) * 100,
      profit_factor: totalLossPnl > 0 ? Math.round((totalWinPnl / totalLossPnl) * 100) / 100 : totalWinPnl > 0 ? 999.99 : 0,
      avg_win_pips:
        wins.length > 0
          ? wins.reduce((s, t) => s + parsePips(t), 0) / wins.length
          : 0,
      avg_loss_pips:
        losses.length > 0
          ? Math.abs(
              losses.reduce((s, t) => s + parsePips(t), 0) / losses.length
            )
          : 0,
      largest_win_usd:
        wins.length > 0 ? Math.max(...wins.map(parsePnl)) : 0,
      largest_loss_usd:
        losses.length > 0 ? Math.min(...losses.map(parsePnl)) : 0,
      max_drawdown_pct: Math.round(maxDrawdownPct * 100) / 100,
      sharpe_ratio: Math.round(sharpe * 100) / 100,
      expectancy_per_trade_usd: Math.round((totalPnl / trades.length) * 100) / 100,
      equity_curve: equityCurve,
    });
  } catch {
    return NextResponse.json(EMPTY_ANALYTICS);
  }
}
