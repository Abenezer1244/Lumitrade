import { NextResponse } from "next/server";
import { backendAuthHeaders } from "@/lib/backend-auth";

export const dynamic = "force-dynamic";

const FALLBACK = {
  balance: "0.00",
  equity: "0.00",
  margin_used: "0.00",
  margin_available: "0.00",
  unrealized_pnl: "0.00",
  open_trade_count: 0,
  daily_pnl_usd: "0.00",
  daily_pnl_pct: "0.00",
  daily_trade_count: 0,
  daily_win_count: 0,
  daily_win_rate: "0.0",
  mode: "PAPER",
};

export async function GET() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.SUPABASE_SERVICE_KEY;
  const backendUrl =
    process.env.BACKEND_URL ||
    "https://lumitrade-engine-production.up.railway.app";

  if (!supabaseUrl || !supabaseKey) return NextResponse.json(FALLBACK);

  try {
    const headers = { apikey: supabaseKey, Authorization: `Bearer ${supabaseKey}` };

    let balance = 0;
    let equity = 0;
    let marginUsed = 0;
    let unrealizedPnl = 0;
    let openTradeCount = 0;
    let mode = "PAPER";
    // `stale` flips true the moment any of the live sources fails so the UI
    // can render a "data may be stale" badge instead of pretending the
    // fallback is the live OANDA balance.
    let stale = false;

    // 1. Fetch REAL OANDA account data from backend /account endpoint
    //    This calls OANDA directly — balance, equity, margin, unrealized P&L
    let accountBreakdown: { forex: object; crypto: object } | undefined;
    try {
      const acctRes = await fetch(`${backendUrl}/account`, {
        headers: backendAuthHeaders(),
        signal: AbortSignal.timeout(5000),
        cache: "no-store",
      });
      if (acctRes.ok) {
        const acct = await acctRes.json();
        balance = acct.balance || 0;
        equity = acct.equity || 0;
        marginUsed = acct.margin_used || 0;
        unrealizedPnl = acct.unrealized_pnl || 0;
        openTradeCount = acct.open_trade_count || 0;
        if (acct.accounts) accountBreakdown = acct.accounts;
      } else {
        stale = true;
        console.error("account: backend /account non-ok", acctRes.status);
      }
    } catch (e) {
      stale = true;
      console.error("account: backend /account fetch failed", e);
    }

    // 2. Fallback: read from system_state if backend /account failed
    if (balance === 0) {
      stale = true;
      try {
        const stateRes = await fetch(
          `${supabaseUrl}/rest/v1/system_state?id=eq.singleton&select=daily_opening_balance,weekly_opening_balance`,
          { headers, cache: "no-store" }
        );
        if (stateRes.ok) {
          const rows = await stateRes.json();
          if (rows?.[0]) {
            balance = parseFloat(rows[0].daily_opening_balance) || 0;
            equity = parseFloat(rows[0].weekly_opening_balance) || balance;
            unrealizedPnl = equity - balance;
          }
        }
      } catch (e) {
        console.error("account: system_state fallback failed", e);
      }
    }

    // 3. Fetch trading mode from health endpoint
    try {
      const healthRes = await fetch(`${backendUrl}/health`, {
        signal: AbortSignal.timeout(5000),
        cache: "no-store",
      });
      if (healthRes.ok) {
        const health = await healthRes.json();
        mode = health?.trading?.mode || "PAPER";
      } else {
        stale = true;
        console.error("account: health endpoint non-ok", healthRes.status);
      }
    } catch (e) {
      stale = true;
      console.error("account: health fetch failed", e);
    }

    const marginAvailable = balance - marginUsed;

    // 4. Today's closed trades for daily stats
    const today = new Date();
    today.setUTCHours(0, 0, 0, 0);
    const closedRes = await fetch(
      `${supabaseUrl}/rest/v1/trades?select=pnl_usd,outcome&status=eq.CLOSED&closed_at=gte.${today.toISOString()}`,
      { headers, cache: "no-store" }
    );
    const todayTrades: { pnl_usd: string; outcome: string }[] = closedRes.ok
      ? await closedRes.json()
      : [];

    const dailyPnl = todayTrades.reduce(
      (s, t) => s + (parseFloat(t.pnl_usd) || 0),
      0
    );
    const dailyTradeCount = todayTrades.length;
    const dailyWinCount = todayTrades.filter((t) => t.outcome === "WIN").length;
    const dailyWinRate =
      dailyTradeCount > 0
        ? ((dailyWinCount / dailyTradeCount) * 100).toFixed(1)
        : "0.0";

    return NextResponse.json({
      balance: balance.toFixed(2),
      equity: equity.toFixed(2),
      margin_used: marginUsed.toFixed(2),
      margin_available: marginAvailable.toFixed(2),
      unrealized_pnl: unrealizedPnl.toFixed(2),
      open_trade_count: openTradeCount,
      daily_pnl_usd: dailyPnl.toFixed(2),
      daily_pnl_pct: balance > 0 ? ((dailyPnl / balance) * 100).toFixed(2) : "0.00",
      daily_trade_count: dailyTradeCount,
      daily_win_count: dailyWinCount,
      daily_win_rate: dailyWinRate,
      mode,
      stale,
      ...(accountBreakdown ? { accounts: accountBreakdown } : {}),
    });
  } catch (e) {
    console.error("account: outer handler failed", e);
    return NextResponse.json({ ...FALLBACK, stale: true });
  }
}
