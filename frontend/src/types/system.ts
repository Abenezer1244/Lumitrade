export type RiskState = "NORMAL" | "CAUTIOUS" | "NEWS_BLOCK" | "DAILY_LIMIT" | "WEEKLY_LIMIT" | "CIRCUIT_OPEN" | "EMERGENCY_HALT";
export type ComponentStatus = "ok" | "degraded" | "offline";

export interface SystemHealth {
  status: "healthy" | "degraded" | "offline";
  instance_id: string;
  is_primary: boolean;
  timestamp: string;
  uptime_seconds: number;
  components: {
    oanda_api: { status: ComponentStatus; latency_ms: number };
    ai_brain: { status: ComponentStatus; last_call_ago_s: number };
    database: { status: ComponentStatus; latency_ms: number };
    price_feed: { status: ComponentStatus; last_tick_ago_s: number };
    risk_engine: { status: ComponentStatus; state: RiskState };
    circuit_breaker: { status: "CLOSED" | "OPEN" | "HALF_OPEN" };
  };
  trading: {
    mode: "PAPER" | "LIVE";
    open_positions: number;
    daily_pnl_usd: number;
    signals_today: number;
  };
}

export interface AccountBreakdown {
  balance: number;
  equity: number;
  unrealized_pnl: number;
  open_trade_count: number;
}

export interface AccountSummary {
  balance: string;
  equity: string;
  margin_used: string;
  margin_available: string;
  unrealized_pnl: string;
  open_trade_count: number;
  daily_pnl_usd: string;
  daily_pnl_pct: string;
  daily_trade_count: number;
  daily_win_count: number;
  daily_win_rate: string;
  mode: "PAPER" | "LIVE";
  stale?: boolean;
  accounts?: {
    forex: AccountBreakdown;
    crypto: AccountBreakdown;
  };
}

export interface PerformanceSummary {
  total_trades: number;
  win_rate: number;
  profit_factor: number;
  avg_win_pips: number;
  avg_loss_pips: number;
  largest_win_usd: number;
  largest_loss_usd: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  expectancy_per_trade_usd: number;
  equity_curve: { date: string; equity: number }[];
  pair_breakdown?: PairPerformance[];
}

export interface PairPerformance {
  pair: string;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  best_trade: number;
  worst_trade: number;
  avg_hold_minutes: number;
}
