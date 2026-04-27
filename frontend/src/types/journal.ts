/**
 * Wire contract for /api/journal — shared between the API route handler and
 * the page consumer to prevent verbatim-duplicate drift.
 */

export interface WeekSummary {
  week_start: string;
  week_end: string;
  trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl_per_trade: number;
  best_pair: string;
  worst_pair: string;
  best_trade: number;
  worst_trade: number;
  avg_confidence: number;
  tp_hit_rate: number;
  sl_hit_rate: number;
  recommendation: string;
}
