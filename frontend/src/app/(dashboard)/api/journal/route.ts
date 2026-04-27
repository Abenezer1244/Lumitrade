import { NextResponse } from "next/server";
import type { Trade as CanonicalTrade } from "@/types/trading";
import type { WeekSummary } from "@/types/journal";
import { supabaseFetch } from "@/lib/api/supabase-rest";

export const dynamic = "force-dynamic";

type Trade = Pick<
  CanonicalTrade,
  | "pair"
  | "direction"
  | "outcome"
  | "pnl_usd"
  | "pnl_pips"
  | "confidence_score"
  | "opened_at"
  | "closed_at"
  | "exit_reason"
>;

function getWeekStart(dateStr: string): string {
  const d = new Date(dateStr);
  const day = d.getUTCDay();
  const diff = d.getUTCDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), diff));
  return monday.toISOString().split("T")[0];
}

function generateRecommendation(summary: WeekSummary): string {
  const lines: string[] = [];

  if (summary.win_rate >= 60) {
    lines.push(`Strong week with ${summary.win_rate.toFixed(0)}% win rate.`);
  } else if (summary.win_rate >= 40) {
    lines.push(`Decent week at ${summary.win_rate.toFixed(0)}% win rate, but room to improve.`);
  } else {
    lines.push(`Tough week with only ${summary.win_rate.toFixed(0)}% win rate. Review losing setups.`);
  }

  if (summary.total_pnl > 0) {
    lines.push(`Net profit of $${summary.total_pnl.toFixed(2)} across ${summary.trades} trades.`);
  } else {
    lines.push(`Net loss of $${Math.abs(summary.total_pnl).toFixed(2)}. Focus on capital preservation.`);
  }

  if (summary.worst_pair) {
    lines.push(`${summary.worst_pair} was the weakest pair this week. Consider reducing exposure.`);
  }

  if (summary.tp_hit_rate < 20) {
    lines.push("Very few trades hit TP. The trailing stop is doing the heavy lifting. Consider tighter TP targets.");
  }

  if (summary.avg_confidence > 0.75) {
    lines.push("Average confidence was high. Verify that high-confidence signals are actually converting.");
  }

  return lines.join(" ");
}

export async function GET() {
  const trades = await supabaseFetch<Trade[]>(
    "/rest/v1/trades?select=pair,direction,outcome,pnl_usd,pnl_pips,confidence_score,opened_at,closed_at,exit_reason&status=eq.CLOSED&order=opened_at.asc"
  );
  if (!trades) return NextResponse.json({ weeks: [] });

  // Group by week
  const weekMap = new Map<string, Trade[]>();
  for (const t of trades) {
    if (!t.opened_at) continue;
    const weekStart = getWeekStart(t.opened_at);
    if (!weekMap.has(weekStart)) weekMap.set(weekStart, []);
    weekMap.get(weekStart)!.push(t);
  }

  // Build summaries
  const weeks: WeekSummary[] = [];

  for (const [weekStart, weekTrades] of Array.from(weekMap.entries())) {
    const wins = weekTrades.filter((t: Trade) => t.outcome === "WIN");
    const losses = weekTrades.filter((t: Trade) => t.outcome === "LOSS");
    const pnls = weekTrades.map((t: Trade) => parseFloat(t.pnl_usd || "0"));
    const totalPnl = pnls.reduce((s: number, v: number) => s + v, 0);

    // Best/worst pair
    const pairPnl: Record<string, number> = {};
    for (const t of weekTrades) {
      pairPnl[t.pair] = (pairPnl[t.pair] || 0) + parseFloat(t.pnl_usd || "0");
    }
    let bestPair = "";
    let worstPair = "";
    let bestPairPnl = -Infinity;
    let worstPairPnl = Infinity;
    for (const pair of Object.keys(pairPnl)) {
      const pnl = pairPnl[pair];
      if (pnl > bestPairPnl) { bestPairPnl = pnl; bestPair = pair; }
      if (pnl < worstPairPnl) { worstPairPnl = pnl; worstPair = pair; }
    }

    const tpHits = weekTrades.filter((t: Trade) => t.exit_reason === "TP_HIT").length;
    const slHits = weekTrades.filter((t: Trade) => t.exit_reason === "SL_HIT").length;
    const avgConf = weekTrades.reduce((s: number, t: Trade) => s + (Number(t.confidence_score) || 0), 0) / weekTrades.length;
    void slHits; // Used in future analytics

    // Week end = week start + 6 days
    const endDate = new Date(weekStart);
    endDate.setUTCDate(endDate.getUTCDate() + 6);

    const summary: WeekSummary = {
      week_start: weekStart,
      week_end: endDate.toISOString().split("T")[0],
      trades: weekTrades.length,
      wins: wins.length,
      losses: losses.length,
      win_rate: weekTrades.length > 0 ? (wins.length / weekTrades.length) * 100 : 0,
      total_pnl: totalPnl,
      avg_pnl_per_trade: weekTrades.length > 0 ? totalPnl / weekTrades.length : 0,
      best_pair: bestPair,
      worst_pair: worstPair,
      best_trade: Math.max(...pnls, 0),
      worst_trade: Math.min(...pnls, 0),
      avg_confidence: avgConf,
      tp_hit_rate: weekTrades.length > 0 ? (tpHits / weekTrades.length) * 100 : 0,
      sl_hit_rate: weekTrades.length > 0 ? (slHits / weekTrades.length) * 100 : 0,
      recommendation: "",
    };

    summary.recommendation = generateRecommendation(summary);
    weeks.push(summary);
  }

  // Most recent first
  weeks.reverse();

  return NextResponse.json({ weeks });
}
