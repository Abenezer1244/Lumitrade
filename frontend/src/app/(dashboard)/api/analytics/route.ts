import { NextResponse } from "next/server";
import { supabaseEnvReady, supabaseFetch } from "@/lib/api/supabase-rest";

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

import type { Trade as CanonicalTrade } from "@/types/trading";

type Trade = Pick<
  CanonicalTrade,
  "pair" | "pnl_usd" | "pnl_pips" | "outcome" | "closed_at" | "opened_at"
>;

type SystemStateRow = { daily_opening_balance: string | null };

export async function GET() {
  if (!supabaseEnvReady()) {
    return NextResponse.json(
      { error: "Server misconfigured: missing SUPABASE_URL or SERVICE_KEY" },
      { status: 500 }
    );
  }

  const trades = await supabaseFetch<Trade[]>(
    "/rest/v1/trades?select=pair,pnl_usd,pnl_pips,outcome,closed_at,opened_at&status=eq.CLOSED&order=closed_at.asc"
  );
  if (!trades || trades.length === 0) {
    return NextResponse.json(EMPTY_ANALYTICS);
  }

  // Fetch real starting balance from OANDA via system_state
  let startingBalance = 100000;
  const balRows = await supabaseFetch<SystemStateRow[]>(
    "/rest/v1/system_state?id=eq.singleton&select=daily_opening_balance"
  );
  if (balRows?.[0]?.daily_opening_balance) {
    startingBalance = parseFloat(balRows[0].daily_opening_balance) || 100000;
  }

  const wins = trades.filter((t) => t.outcome === "WIN");
  const losses = trades.filter((t) => t.outcome === "LOSS");

  const parsePnl = (t: Trade) => parseFloat(t.pnl_usd || "0") || 0;
  const parsePips = (t: Trade) => parseFloat(t.pnl_pips || "0") || 0;

  const totalPnl = trades.reduce((s, t) => s + parsePnl(t), 0);
  const totalWinPnl = wins.reduce((s, t) => s + parsePnl(t), 0);
  const totalLossPnl = Math.abs(losses.reduce((s, t) => s + parsePnl(t), 0));

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

  // Per-pair breakdown
  const pairMap = new Map<string, Trade[]>();
  for (const t of trades) {
    const p = t.pair || "UNKNOWN";
    if (!pairMap.has(p)) pairMap.set(p, []);
    pairMap.get(p)!.push(t);
  }

  const pairBreakdown = Array.from(pairMap.entries())
    .map(([pair, pts]) => {
      const pWins = pts.filter((t) => t.outcome === "WIN");
      const pLosses = pts.filter((t) => t.outcome === "LOSS");
      const pTotalPnl = pts.reduce((s, t) => s + parsePnl(t), 0);
      const pAvgPnl = pts.length > 0 ? pTotalPnl / pts.length : 0;

      // Average hold time in minutes
      let avgHoldMin = 0;
      const holdTimes = pts
        .filter((t) => t.opened_at && t.closed_at)
        .map(
          (t) =>
            (new Date(t.closed_at!).getTime() -
              new Date(t.opened_at!).getTime()) /
            60000
        );
      if (holdTimes.length > 0) {
        avgHoldMin = holdTimes.reduce((a, b) => a + b, 0) / holdTimes.length;
      }

      return {
        pair,
        total_trades: pts.length,
        wins: pWins.length,
        losses: pLosses.length,
        win_rate: pts.length > 0 ? (pWins.length / pts.length) * 100 : 0,
        total_pnl: Math.round(pTotalPnl * 100) / 100,
        avg_pnl: Math.round(pAvgPnl * 100) / 100,
        best_trade: pts.length > 0 ? Math.max(...pts.map(parsePnl)) : 0,
        worst_trade: pts.length > 0 ? Math.min(...pts.map(parsePnl)) : 0,
        avg_hold_minutes: Math.round(avgHoldMin),
      };
    })
    .sort((a, b) => b.total_pnl - a.total_pnl);

  return NextResponse.json({
    total_trades: trades.length,
    win_rate: (wins.length / trades.length) * 100,
    profit_factor:
      totalLossPnl > 0
        ? Math.round((totalWinPnl / totalLossPnl) * 100) / 100
        : totalWinPnl > 0
        ? 999.99
        : 0,
    avg_win_pips:
      wins.length > 0 ? wins.reduce((s, t) => s + parsePips(t), 0) / wins.length : 0,
    avg_loss_pips:
      losses.length > 0
        ? Math.abs(losses.reduce((s, t) => s + parsePips(t), 0) / losses.length)
        : 0,
    largest_win_usd: wins.length > 0 ? Math.max(...wins.map(parsePnl)) : 0,
    largest_loss_usd: losses.length > 0 ? Math.min(...losses.map(parsePnl)) : 0,
    max_drawdown_pct: Math.round(maxDrawdownPct * 100) / 100,
    sharpe_ratio: Math.round(sharpe * 100) / 100,
    expectancy_per_trade_usd: Math.round((totalPnl / trades.length) * 100) / 100,
    equity_curve: equityCurve,
    pair_breakdown: pairBreakdown,
  });
}
