"use client";
import type { Signal } from "@/types/trading";
import { formatPrice } from "@/lib/formatters";
import TimeframeScores from "./TimeframeScores";

interface Props {
  signal: Signal;
}

export default function SignalDetailPanel({ signal }: Props) {
  const entry = parseFloat(signal.entry_price);
  const sl = parseFloat(signal.stop_loss);
  const tp = parseFloat(signal.take_profit);
  const riskPips = Math.abs(entry - sl);
  const rewardPips = Math.abs(tp - entry);
  const rr = riskPips > 0 ? (rewardPips / riskPips).toFixed(1) : "---";

  const adjustmentEntries = Object.entries(signal.confidence_adjustment_log || {});
  const rawPct = Math.round(signal.confidence_raw * 100);
  const adjPct = Math.round(signal.confidence_adjusted * 100);

  const indicators = signal.indicators_snapshot;
  const indicatorRows = [
    { label: "RSI (14)", value: indicators.rsi_14 },
    { label: "MACD Line", value: indicators.macd_line },
    { label: "MACD Signal", value: indicators.macd_signal },
    { label: "MACD Histogram", value: indicators.macd_histogram },
    { label: "EMA 20", value: indicators.ema_20 },
    { label: "EMA 50", value: indicators.ema_50 },
    { label: "EMA 200", value: indicators.ema_200 },
    { label: "ATR (14)", value: indicators.atr_14 },
    { label: "BB Upper", value: indicators.bb_upper },
    { label: "BB Mid", value: indicators.bb_mid },
    { label: "BB Lower", value: indicators.bb_lower },
  ];

  const pair = signal.pair;

  return (
    <div className="space-y-4 pt-3 border-t border-border">
      {/* Entry / SL / TP Price Boxes */}
      <div className="grid grid-cols-3 gap-2">
        <div className="glass-elevated p-3 text-center">
          <p className="text-label text-tertiary mb-1">Entry</p>
          <p className="text-sm font-mono text-primary">{formatPrice(signal.entry_price, pair)}</p>
        </div>
        <div className="glass-elevated p-3 text-center">
          <p className="text-label text-tertiary mb-1">Stop Loss</p>
          <p className="text-sm font-mono text-loss">{formatPrice(signal.stop_loss, pair)}</p>
        </div>
        <div className="glass-elevated p-3 text-center">
          <p className="text-label text-tertiary mb-1">Take Profit</p>
          <p className="text-sm font-mono text-profit">{formatPrice(signal.take_profit, pair)}</p>
        </div>
      </div>

      {/* RR Ratio + Spread */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-label text-tertiary">R:R</span>
          <span className="text-sm font-mono text-primary">1:{rr}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-label text-tertiary">Spread</span>
          <span className="text-sm font-mono text-secondary">{signal.spread_pips}p</span>
        </div>
      </div>

      {/* Timeframe Scores */}
      <div>
        <p className="text-label text-tertiary mb-2">Timeframe Scores</p>
        <TimeframeScores scores={signal.timeframe_scores} />
      </div>

      {/* Indicator Table */}
      <div>
        <p className="text-label text-tertiary mb-2">Indicators</p>
        <div className="glass-elevated overflow-hidden">
          <table className="w-full text-xs">
            <tbody>
              {indicatorRows.map(({ label, value }) => (
                <tr key={label} className="border-b border-border last:border-b-0">
                  <td className="px-3 py-1.5 text-secondary">{label}</td>
                  <td className="px-3 py-1.5 font-mono text-primary text-right">{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Confidence Adjustment Breakdown */}
      <div>
        <p className="text-label text-tertiary mb-2">Confidence Adjustment</p>
        <div className="glass-elevated p-3 space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-secondary">Raw Score</span>
            <span className="font-mono text-primary">{rawPct}%</span>
          </div>
          {adjustmentEntries.map(([key, delta]) => {
            const sign = delta >= 0 ? "+" : "";
            const colorClass = delta > 0 ? "text-profit" : delta < 0 ? "text-loss" : "text-secondary";
            return (
              <div key={key} className="flex justify-between text-xs">
                <span className="text-secondary">{key.replace(/_/g, " ")}</span>
                <span className={`font-mono ${colorClass}`}>{sign}{Math.round(delta * 100)}%</span>
              </div>
            );
          })}
          <div className="flex justify-between text-xs border-t border-border pt-1 mt-1">
            <span className="text-primary font-medium">Adjusted Score</span>
            <span className="font-mono text-primary font-bold">{adjPct}%</span>
          </div>
        </div>
      </div>

      {/* News Context */}
      {signal.news_context && signal.news_context.length > 0 && (
        <div>
          <p className="text-label text-tertiary mb-2">News Context</p>
          <div className="space-y-1.5">
            {signal.news_context.map((event, i) => {
              const impactColor =
                event.impact === "HIGH" ? "text-loss" :
                event.impact === "MEDIUM" ? "text-warning" : "text-secondary";
              return (
                <div key={i} className="glass-elevated px-3 py-2 flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-primary truncate">{event.title}</p>
                    <p className="text-[10px] text-tertiary">{event.currencies_affected.join(", ")}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <span className={`text-[10px] font-bold uppercase ${impactColor}`}>{event.impact}</span>
                    <p className="text-[10px] text-tertiary font-mono">
                      {event.minutes_until > 0 ? `in ${event.minutes_until}m` : `${Math.abs(event.minutes_until)}m ago`}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Analyst Briefing (SA-01 feature) */}
      {signal.analyst_briefing && (
        <div>
          <p className="text-label text-tertiary mb-2">Analyst Briefing</p>
          <div className="glass-elevated p-3">
            <p className="text-xs text-primary leading-relaxed">{signal.analyst_briefing}</p>
          </div>
        </div>
      )}

      {/* Full AI Reasoning */}
      <div>
        <p className="text-label text-tertiary mb-2">AI Reasoning</p>
        <div className="glass-elevated p-3">
          <p className="text-xs font-mono text-secondary leading-relaxed whitespace-pre-wrap">{signal.reasoning}</p>
        </div>
      </div>
    </div>
  );
}
