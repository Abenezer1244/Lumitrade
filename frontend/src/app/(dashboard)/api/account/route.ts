import { NextResponse } from "next/server";

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

    // 1. Fetch REAL OANDA balance/equity from backend /prices won't help,
    //    but the health endpoint has open_trades count.
    //    The real balance comes from system_state (backend updates every 5s).
    let balance = 0;
    let equity = 0;
    let marginUsed = 0;
    let openingBalance = 0;
    let mode = "PAPER";

    try {
      const stateRes = await fetch(
        `${supabaseUrl}/rest/v1/system_state?id=eq.singleton&select=daily_opening_balance,weekly_opening_balance`,
        { headers, cache: "no-store" }
      );
      if (stateRes.ok) {
        const rows = await stateRes.json();
        if (rows?.[0]) {
          openingBalance = parseFloat(rows[0].daily_opening_balance) || 100000;
        }
      }
    } catch { /* continue */ }

    // 2. Fetch live OANDA account summary via backend
    //    The backend persists balance to system_state, but let's get it from
    //    the OANDA account directly via our prices-style endpoint.
    //    For now, use the health endpoint which has trading info.
    try {
      const healthRes = await fetch(`${backendUrl}/health`, {
        signal: AbortSignal.timeout(5000),
        cache: "no-store",
      });
      if (healthRes.ok) {
        const health = await healthRes.json();
        mode = health?.trading?.mode || "PAPER";
      }
    } catch { /* continue */ }

    // 3. Fetch OANDA account from the accounts table or system_state
    //    The backend writes the real OANDA balance to system_state every 5s
    try {
      const accRes = await fetch(
        `${supabaseUrl}/rest/v1/accounts?select=balance,equity,margin_used&limit=1&order=updated_at.desc`,
        { headers, cache: "no-store" }
      );
      if (accRes.ok) {
        const accounts = await accRes.json();
        if (accounts?.[0]) {
          balance = parseFloat(accounts[0].balance) || 0;
          equity = parseFloat(accounts[0].equity) || balance;
          marginUsed = parseFloat(accounts[0].margin_used) || 0;
        }
      }
    } catch { /* continue */ }

    // Fallback: use daily_opening_balance as OANDA balance
    if (balance === 0 && openingBalance > 0) {
      balance = openingBalance;
      equity = openingBalance;
    }

    const marginAvailable = balance - marginUsed;
    const unrealizedPnl = equity - balance;

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

    // Daily P&L = sum of today's closed trades P&L (from our system)
    // Note: this may differ from OANDA's balance change if broker_trade_id was empty
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

    // Open positions from DB
    const openRes = await fetch(
      `${supabaseUrl}/rest/v1/trades?select=id&status=eq.OPEN`,
      { headers, cache: "no-store" }
    );
    const openTrades = openRes.ok ? await openRes.json() : [];

    return NextResponse.json({
      balance: balance.toFixed(2),
      equity: equity.toFixed(2),
      margin_used: marginUsed.toFixed(2),
      margin_available: marginAvailable.toFixed(2),
      unrealized_pnl: unrealizedPnl.toFixed(2),
      open_trade_count: openTrades.length || 0,
      daily_pnl_usd: dailyPnl.toFixed(2),
      daily_pnl_pct: balance > 0 ? ((dailyPnl / balance) * 100).toFixed(2) : "0.00",
      daily_trade_count: dailyTradeCount,
      daily_win_count: dailyWinCount,
      daily_win_rate: dailyWinRate,
      mode,
    });
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
