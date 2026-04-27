/**
 * Wire contract for /api/intelligence — shared between the API route handler
 * and the page consumer to prevent verbatim-duplicate drift.
 */

export interface PairStat {
  pair: string;
  trades: number;
  wins: number;
  winRate: number;
  pnlUsd: number;
}

export interface SessionStat {
  hour: number;
  trades: number;
  wins: number;
  pnlUsd: number;
}

export interface RiskAssessment {
  maxDrawdownUsd: number;
  maxConsecutiveLosses: number;
  averageLossUsd: number;
  riskRewardRatio: number;
  largestWinUsd: number;
  largestLossUsd: number;
}

export interface WeeklyReport {
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
