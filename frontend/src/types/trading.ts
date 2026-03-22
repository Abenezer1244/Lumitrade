export type Action = "BUY" | "SELL" | "HOLD";
export type Direction = "BUY" | "SELL";
export type TradingMode = "PAPER" | "LIVE";
export type Outcome = "WIN" | "LOSS" | "BREAKEVEN";
export type Session = "LONDON" | "NEW_YORK" | "OVERLAP" | "TOKYO" | "OTHER";
export type ExitReason = "SL_HIT" | "TP_HIT" | "AI_CLOSE" | "MANUAL" | "EMERGENCY" | "UNKNOWN";
export type GenerationMethod = "AI" | "RULE_BASED";

export interface Signal {
  id: string;
  pair: string;
  action: Action;
  confidence_raw: number;
  confidence_adjusted: number;
  confidence_adjustment_log: Record<string, number>;
  entry_price: string;
  stop_loss: string;
  take_profit: string;
  summary: string;
  reasoning: string;
  timeframe_scores: { h4: number; h1: number; m15: number };
  indicators_snapshot: IndicatorSnapshot;
  key_levels: string[];
  news_context: NewsEvent[];
  session: Session;
  spread_pips: string;
  executed: boolean;
  rejection_reason: string | null;
  generation_method: GenerationMethod;
  created_at: string;
  analyst_briefing?: string;
}

export interface IndicatorSnapshot {
  rsi_14: string;
  macd_line: string;
  macd_signal: string;
  macd_histogram: string;
  ema_20: string;
  ema_50: string;
  ema_200: string;
  atr_14: string;
  bb_upper: string;
  bb_mid: string;
  bb_lower: string;
}

export interface NewsEvent {
  title: string;
  currencies_affected: string[];
  impact: "HIGH" | "MEDIUM" | "LOW";
  scheduled_at: string;
  minutes_until: number;
}

export interface Trade {
  id: string;
  signal_id: string | null;
  broker_trade_id: string | null;
  pair: string;
  direction: Direction;
  mode: TradingMode;
  entry_price: string;
  exit_price: string | null;
  stop_loss: string;
  take_profit: string;
  position_size: number;
  confidence_score: number | null;
  slippage_pips: string | null;
  pnl_pips: string | null;
  pnl_usd: string | null;
  status: "OPEN" | "CLOSED" | "CANCELLED";
  exit_reason: ExitReason | null;
  outcome: Outcome | null;
  session: Session | null;
  opened_at: string;
  closed_at: string | null;
  duration_minutes: number | null;
}

export interface OpenPosition extends Trade {
  live_pnl_pips: number;
  live_pnl_usd: number;
  current_price: string;
}
