export type MarketRegime = "TRENDING" | "RANGING" | "HIGH_VOLATILITY" | "LOW_LIQUIDITY" | "UNKNOWN";
export type CurrencySentiment = "BULLISH" | "BEARISH" | "NEUTRAL";
export type AssetClass = "FOREX" | "CRYPTO" | "STOCKS" | "OPTIONS";

export interface RuinAnalysis {
  prob_loss_25pct: number;
  prob_loss_50pct: number;
  prob_loss_100pct: number;
  status: "SAFE" | "WARNING" | "DANGER" | "INSUFFICIENT_DATA";
  sample_size: number;
  is_sufficient: boolean;
}
