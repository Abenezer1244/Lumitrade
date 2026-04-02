import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/* ── Types ─────────────────────────────────────────────────── */

interface ClosedTrade {
  id: string;
  pair: string;
  direction: "BUY" | "SELL";
  outcome: "WIN" | "LOSS" | "BREAKEVEN" | null;
  pnl_usd: string | null;
  pnl_pips: string | null;
  confidence_score: number | null;
  opened_at: string;
  closed_at: string | null;
  exit_reason: string | null;
}

interface PairStat {
  pair: string;
  trades: number;
  wins: number;
  winRate: number;
  pnlUsd: number;
}

interface SessionStat {
  hour: number;
  trades: number;
  wins: number;
  pnlUsd: number;
}

interface RiskAssessment {
  maxDrawdownUsd: number;
  maxConsecutiveLosses: number;
  averageLossUsd: number;
  riskRewardRatio: number;
  largestWinUsd: number;
  largestLossUsd: number;
}

interface WeeklyReport {
  weekStart: string;
  weekEnd: string;
  totalTrades: number;
  wins: number;
  losses: number;
  breakevens: number;
  winRate: number;
  totalPnlUsd: number;
  totalPnlPips: number;
  pairStats: PairStat[];
  sessionStats: SessionStat[];
  riskAssessment: RiskAssessment;
  recommendations: string[];
}

/* ── Helpers ───────────────────────────────────────────────── */

function getMonday(d: Date): Date {
  const date = new Date(d);
  const day = date.getUTCDay();
  const diff = day === 0 ? -6 : 1 - day;
  date.setUTCDate(date.getUTCDate() + diff);
  date.setUTCHours(0, 0, 0, 0);
  return date;
}

function getSunday(monday: Date): Date {
  const date = new Date(monday);
  date.setUTCDate(date.getUTCDate() + 6);
  date.setUTCHours(23, 59, 59, 999);
  return date;
}

function formatDateRange(monday: Date): string {
  return monday.toISOString().split("T")[0];
}

function safeFloat(val: string | number | null): number {
  if (val === null || val === undefined) return 0;
  const n = typeof val === "string" ? parseFloat(val) : val;
  return isNaN(n) ? 0 : n;
}

function groupByWeek(trades: ClosedTrade[]): Map<string, ClosedTrade[]> {
  const weeks = new Map<string, ClosedTrade[]>();
  for (const trade of trades) {
    const closedDate = trade.closed_at ? new Date(trade.closed_at) : new Date(trade.opened_at);
    const monday = getMonday(closedDate);
    const key = formatDateRange(monday);
    if (!weeks.has(key)) weeks.set(key, []);
    weeks.get(key)!.push(trade);
  }
  return weeks;
}

function computePairStats(trades: ClosedTrade[]): PairStat[] {
  const map = new Map<string, { trades: number; wins: number; pnlUsd: number }>();
  for (const t of trades) {
    const stat = map.get(t.pair) ?? { trades: 0, wins: 0, pnlUsd: 0 };
    stat.trades++;
    if (t.outcome === "WIN") stat.wins++;
    stat.pnlUsd += safeFloat(t.pnl_usd);
    map.set(t.pair, stat);
  }
  return Array.from(map.entries())
    .map(([pair, s]) => ({
      pair,
      trades: s.trades,
      wins: s.wins,
      winRate: s.trades > 0 ? Math.round((s.wins / s.trades) * 100) : 0,
      pnlUsd: Math.round(s.pnlUsd * 100) / 100,
    }))
    .sort((a, b) => b.pnlUsd - a.pnlUsd);
}

function computeSessionStats(trades: ClosedTrade[]): SessionStat[] {
  const hours: SessionStat[] = Array.from({ length: 24 }, (_, i) => ({
    hour: i,
    trades: 0,
    wins: 0,
    pnlUsd: 0,
  }));
  for (const t of trades) {
    const hour = new Date(t.opened_at).getUTCHours();
    hours[hour].trades++;
    if (t.outcome === "WIN") hours[hour].wins++;
    hours[hour].pnlUsd += safeFloat(t.pnl_usd);
  }
  // Round pnl values
  for (const h of hours) {
    h.pnlUsd = Math.round(h.pnlUsd * 100) / 100;
  }
  return hours;
}

function computeRiskAssessment(trades: ClosedTrade[]): RiskAssessment {
  let maxDrawdown = 0;
  let runningPnl = 0;
  let peak = 0;
  let consecutiveLosses = 0;
  let maxConsecutiveLosses = 0;
  let totalLoss = 0;
  let lossCount = 0;
  let totalWin = 0;
  let winCount = 0;
  let largestWin = 0;
  let largestLoss = 0;

  // Sort chronologically for drawdown calculation
  const sorted = [...trades].sort(
    (a, b) => new Date(a.closed_at ?? a.opened_at).getTime() - new Date(b.closed_at ?? b.opened_at).getTime()
  );

  for (const t of sorted) {
    const pnl = safeFloat(t.pnl_usd);
    runningPnl += pnl;
    if (runningPnl > peak) peak = runningPnl;
    const dd = peak - runningPnl;
    if (dd > maxDrawdown) maxDrawdown = dd;

    if (t.outcome === "LOSS") {
      consecutiveLosses++;
      if (consecutiveLosses > maxConsecutiveLosses) maxConsecutiveLosses = consecutiveLosses;
      totalLoss += Math.abs(pnl);
      lossCount++;
      if (Math.abs(pnl) > Math.abs(largestLoss)) largestLoss = pnl;
    } else {
      consecutiveLosses = 0;
    }

    if (t.outcome === "WIN") {
      totalWin += pnl;
      winCount++;
      if (pnl > largestWin) largestWin = pnl;
    }
  }

  const avgLoss = lossCount > 0 ? totalLoss / lossCount : 0;
  const avgWin = winCount > 0 ? totalWin / winCount : 0;
  const rr = avgLoss > 0 ? avgWin / avgLoss : 0;

  return {
    maxDrawdownUsd: Math.round(maxDrawdown * 100) / 100,
    maxConsecutiveLosses,
    averageLossUsd: Math.round(avgLoss * 100) / 100,
    riskRewardRatio: Math.round(rr * 100) / 100,
    largestWinUsd: Math.round(largestWin * 100) / 100,
    largestLossUsd: Math.round(largestLoss * 100) / 100,
  };
}

function generateRecommendations(
  pairStats: PairStat[],
  sessionStats: SessionStat[],
  risk: RiskAssessment,
  winRate: number,
  totalPnl: number
): string[] {
  const recs: string[] = [];

  // Pair recommendations
  const profitablePairs = pairStats.filter((p) => p.pnlUsd > 0 && p.trades >= 2);
  const unprofitablePairs = pairStats.filter((p) => p.pnlUsd < 0 && p.trades >= 2);

  if (profitablePairs.length > 0) {
    const top = profitablePairs[0];
    recs.push(
      `Focus on ${top.pair.replace("_", "/")} which had a ${top.winRate}% win rate across ${top.trades} trades with +$${top.pnlUsd.toFixed(2)} P&L.`
    );
  }

  if (unprofitablePairs.length > 0) {
    const worst = unprofitablePairs[unprofitablePairs.length - 1];
    recs.push(
      `Review ${worst.pair.replace("_", "/")} strategy — ${worst.winRate}% win rate with -$${Math.abs(worst.pnlUsd).toFixed(2)} loss across ${worst.trades} trades.`
    );
  }

  // Session recommendations
  const activeSessions = sessionStats.filter((s) => s.trades >= 2);
  const bestSession = activeSessions.sort((a, b) => b.pnlUsd - a.pnlUsd)[0];
  const worstSession = activeSessions.sort((a, b) => a.pnlUsd - b.pnlUsd)[0];

  if (bestSession && bestSession.pnlUsd > 0) {
    recs.push(
      `Best trading hour: ${bestSession.hour.toString().padStart(2, "0")}:00 UTC with +$${bestSession.pnlUsd.toFixed(2)} across ${bestSession.trades} trades.`
    );
  }

  if (worstSession && worstSession.pnlUsd < 0) {
    recs.push(
      `Avoid trading at ${worstSession.hour.toString().padStart(2, "0")}:00 UTC — lost $${Math.abs(worstSession.pnlUsd).toFixed(2)} in ${worstSession.trades} trades.`
    );
  }

  // Risk recommendations
  if (risk.maxConsecutiveLosses >= 3) {
    recs.push(
      `Had ${risk.maxConsecutiveLosses} consecutive losses. Consider reducing position size after 2 consecutive losses.`
    );
  }

  if (risk.riskRewardRatio < 1.5 && risk.riskRewardRatio > 0) {
    recs.push(
      `Risk-reward ratio is ${risk.riskRewardRatio.toFixed(2)}:1. Aim for at least 1.5:1 by widening take-profit or tightening stop-loss.`
    );
  }

  if (winRate < 50 && totalPnl < 0) {
    recs.push(
      `Win rate is ${winRate}%. Review entry criteria and consider higher confidence thresholds for trade signals.`
    );
  }

  if (winRate >= 60 && totalPnl > 0) {
    recs.push(
      `Strong ${winRate}% win rate this week. Maintain current strategy discipline.`
    );
  }

  // If we have no meaningful recs, add a generic one
  if (recs.length === 0) {
    recs.push("Continue monitoring trade performance. More data needed for specific recommendations.");
  }

  return recs;
}

function buildWeeklyReport(weekKey: string, trades: ClosedTrade[]): WeeklyReport {
  const monday = new Date(weekKey + "T00:00:00Z");
  const sunday = getSunday(monday);

  const wins = trades.filter((t) => t.outcome === "WIN").length;
  const losses = trades.filter((t) => t.outcome === "LOSS").length;
  const breakevens = trades.filter((t) => t.outcome === "BREAKEVEN").length;
  const totalPnlUsd = trades.reduce((sum, t) => sum + safeFloat(t.pnl_usd), 0);
  const totalPnlPips = trades.reduce((sum, t) => sum + safeFloat(t.pnl_pips), 0);
  const winRate = trades.length > 0 ? Math.round((wins / trades.length) * 100) : 0;

  const pairStats = computePairStats(trades);
  const sessionStats = computeSessionStats(trades);
  const riskAssessment = computeRiskAssessment(trades);
  const recommendations = generateRecommendations(pairStats, sessionStats, riskAssessment, winRate, totalPnlUsd);

  return {
    weekStart: formatDateRange(monday),
    weekEnd: formatDateRange(sunday),
    totalTrades: trades.length,
    wins,
    losses,
    breakevens,
    winRate,
    totalPnlUsd: Math.round(totalPnlUsd * 100) / 100,
    totalPnlPips: Math.round(totalPnlPips * 100) / 100,
    pairStats,
    sessionStats,
    riskAssessment,
    recommendations,
  };
}

/* ── Route Handler ─────────────────────────────────────────── */

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
    const headers = { apikey: key, Authorization: `Bearer ${key}` };

    // Fetch all closed trades
    const tradesRes = await fetch(
      `${url}/rest/v1/trades?select=id,pair,direction,outcome,pnl_usd,pnl_pips,confidence_score,opened_at,closed_at,exit_reason&status=eq.CLOSED&order=closed_at.desc`,
      { headers, cache: "no-store" }
    );

    if (!tradesRes.ok) {
      return NextResponse.json({ reports: [] });
    }

    const trades: ClosedTrade[] = (await tradesRes.json()) ?? [];

    if (trades.length === 0) {
      return NextResponse.json({ reports: [] });
    }

    // Group by week (Monday-Sunday)
    const weeks = groupByWeek(trades);

    // Build reports, sorted newest first
    const reports: WeeklyReport[] = Array.from(weeks.entries())
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([weekKey, weekTrades]) => buildWeeklyReport(weekKey, weekTrades));

    return NextResponse.json({ reports });
  } catch {
    return NextResponse.json({ reports: [] });
  }
}
