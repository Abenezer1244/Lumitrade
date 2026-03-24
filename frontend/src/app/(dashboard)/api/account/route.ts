import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const FALLBACK = {
  balance: "0.00",
  equity: "0.00",
  margin_used: "0.00",
  margin_available: "0.00",
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

    // Fetch real account data from backend health endpoint
    let balance = "0.00";
    let equity = "0.00";
    let marginUsed = "0.00";
    let marginAvailable = "0.00";
    let mode = "PAPER";

    try {
      const healthRes = await fetch(`${backendUrl}/health`, {
        signal: AbortSignal.timeout(5000),
        cache: "no-store",
      });
      if (healthRes.ok) {
        const health = await healthRes.json();
        mode = health?.trading?.mode || "PAPER";
      }
    } catch {
      // Backend unreachable — continue with DB data
    }

    // Fetch OANDA account data via backend (if it exposes it) or from system_state
    try {
      const stateRes = await fetch(
        `${supabaseUrl}/rest/v1/system_state?id=eq.singleton&select=*`,
        { headers, cache: "no-store" }
      );
      if (stateRes.ok) {
        const rows = await stateRes.json();
        if (rows?.[0]) {
          const state = rows[0];
          if (state.daily_opening_balance) balance = String(state.daily_opening_balance);
          if (state.weekly_opening_balance) equity = String(state.weekly_opening_balance);
          // Get mode from state if health endpoint returned UNKNOWN
          if (mode === "PAPER" || mode === "UNKNOWN") {
            mode = state.trading_mode || "PAPER";
          }
        }
      }
    } catch {
      // DB unreachable
    }

    // If no balance from system_state, try accounts table
    if (balance === "0.00") {
      try {
        const accRes = await fetch(
          `${supabaseUrl}/rest/v1/accounts?select=balance,equity,margin_used&limit=1&order=updated_at.desc`,
          { headers, cache: "no-store" }
        );
        if (accRes.ok) {
          const accounts = await accRes.json();
          if (accounts?.[0]) {
            balance = String(accounts[0].balance || "0.00");
            equity = String(accounts[0].equity || balance);
            marginUsed = String(accounts[0].margin_used || "0.00");
            const bal = parseFloat(balance);
            const mu = parseFloat(marginUsed);
            marginAvailable = (bal - mu).toFixed(2);
          }
        }
      } catch {
        // accounts table may not exist or be empty
      }
    }

    // Open trades count
    const openRes = await fetch(
      `${supabaseUrl}/rest/v1/trades?select=id&status=eq.OPEN`,
      { headers, cache: "no-store" }
    );
    const openTrades = openRes.ok ? await openRes.json() : [];

    // Today's closed trades for daily stats
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
    const dailyWinCount = todayTrades.filter(
      (t) => t.outcome === "WIN"
    ).length;
    const bal = parseFloat(balance) || 1;
    const dailyWinRate =
      dailyTradeCount > 0
        ? ((dailyWinCount / dailyTradeCount) * 100).toFixed(1)
        : "0.0";

    return NextResponse.json({
      balance,
      equity: equity || balance,
      margin_used: marginUsed,
      margin_available: marginAvailable || balance,
      open_trade_count: openTrades.length || 0,
      daily_pnl_usd: dailyPnl.toFixed(2),
      daily_pnl_pct: ((dailyPnl / bal) * 100).toFixed(2),
      daily_trade_count: dailyTradeCount,
      daily_win_count: dailyWinCount,
      daily_win_rate: dailyWinRate,
      mode,
    });
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
