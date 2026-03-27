"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { motion } from "motion/react";
import { BarChart3, RefreshCw } from "lucide-react";

interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface TradeMarker {
  time: number;
  price: number;
  direction: "BUY" | "SELL";
  type: "entry" | "sl" | "tp" | "close";
}

interface PriceChartProps {
  pair?: string;
  trades?: {
    opened_at: string;
    closed_at?: string;
    entry_price: number;
    exit_price?: number;
    stop_loss: number;
    take_profit: number;
    direction: string;
    status: string;
  }[];
}

const PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD", "USD_CAD", "NZD_USD", "XAU_USD"];
const TIMEFRAMES = [
  { label: "15m", value: "M15" },
  { label: "1H", value: "H1" },
  { label: "4H", value: "H4" },
  { label: "1D", value: "D" },
];

function formatPair(pair: string): string {
  return pair.replace("_", "/");
}

export default function PriceChart({ pair: initialPair, trades }: PriceChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof import("lightweight-charts").createChart> | null>(null);
  const seriesRef = useRef<ReturnType<ReturnType<typeof import("lightweight-charts").createChart>["addCandlestickSeries"]> | null>(null);

  const [selectedPair, setSelectedPair] = useState(initialPair || "EUR_USD");
  const [selectedTf, setSelectedTf] = useState("H1");
  const [loading, setLoading] = useState(true);
  const [lastPrice, setLastPrice] = useState<number | null>(null);
  const [priceChange, setPriceChange] = useState<number>(0);

  const fetchCandles = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/candles?pair=${selectedPair}&granularity=${selectedTf}&count=150`);
      if (!res.ok) return;
      const data = await res.json();
      const candles: Candle[] = data.candles || [];

      if (candles.length > 0 && seriesRef.current) {
        seriesRef.current.setData(
          candles.map((c) => ({
            time: c.time as import("lightweight-charts").UTCTimestamp,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          }))
        );

        const last = candles[candles.length - 1];
        const prev = candles.length > 1 ? candles[candles.length - 2] : last;
        setLastPrice(last.close);
        setPriceChange(((last.close - prev.close) / prev.close) * 100);

        // Add trade markers as horizontal lines
        if (trades && chartRef.current) {
          for (const trade of trades) {
            if (trade.status === "OPEN") {
              // Entry line
              const entrySeries = chartRef.current.addLineSeries({
                color: trade.direction === "BUY" ? "#00C896" : "#FF4D6A",
                lineWidth: 1,
                lineStyle: 0, // Solid
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false,
              });
              const entryTime = candles[candles.length - 20]?.time || candles[0].time;
              const lastTime = candles[candles.length - 1].time;
              entrySeries.setData([
                { time: entryTime as import("lightweight-charts").UTCTimestamp, value: trade.entry_price },
                { time: lastTime as import("lightweight-charts").UTCTimestamp, value: trade.entry_price },
              ]);

              // SL line (dashed red)
              const slSeries = chartRef.current.addLineSeries({
                color: "#FF4D6A",
                lineWidth: 1,
                lineStyle: 2, // Dashed
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false,
              });
              slSeries.setData([
                { time: entryTime as import("lightweight-charts").UTCTimestamp, value: trade.stop_loss },
                { time: lastTime as import("lightweight-charts").UTCTimestamp, value: trade.stop_loss },
              ]);

              // TP line (dashed green)
              const tpSeries = chartRef.current.addLineSeries({
                color: "#00C896",
                lineWidth: 1,
                lineStyle: 2,
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false,
              });
              tpSeries.setData([
                { time: entryTime as import("lightweight-charts").UTCTimestamp, value: trade.take_profit },
                { time: lastTime as import("lightweight-charts").UTCTimestamp, value: trade.take_profit },
              ]);
            }
          }
        }

        chartRef.current?.timeScale().fitContent();
      }
    } catch (e) {
      console.error("Failed to fetch candles:", e);
    } finally {
      setLoading(false);
    }
  }, [selectedPair, selectedTf, trades]);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    let chart: ReturnType<typeof import("lightweight-charts").createChart>;

    const initChart = async () => {
      const { createChart, ColorType, CrosshairMode } = await import("lightweight-charts");

      // Get CSS variable values
      const computedStyle = getComputedStyle(document.documentElement);
      const bgColor = computedStyle.getPropertyValue("--color-bg-surface-solid").trim() || "#111D2E";
      const textColor = computedStyle.getPropertyValue("--color-text-tertiary").trim() || "#6B7280";
      const borderColor = computedStyle.getPropertyValue("--color-border").trim() || "rgba(30, 58, 95, 0.6)";

      chart = createChart(chartContainerRef.current!, {
        layout: {
          background: { type: ColorType.Solid, color: "transparent" },
          textColor: textColor,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 10,
        },
        grid: {
          vertLines: { color: borderColor, style: 3 },
          horzLines: { color: borderColor, style: 3 },
        },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: { color: textColor, width: 1, style: 3, labelBackgroundColor: bgColor },
          horzLine: { color: textColor, width: 1, style: 3, labelBackgroundColor: bgColor },
        },
        timeScale: {
          borderColor: borderColor,
          timeVisible: true,
          secondsVisible: false,
        },
        rightPriceScale: {
          borderColor: borderColor,
        },
        handleScroll: { vertTouchDrag: false },
      });

      const series = chart.addCandlestickSeries({
        upColor: "#00C896",
        downColor: "#FF4D6A",
        borderUpColor: "#00C896",
        borderDownColor: "#FF4D6A",
        wickUpColor: "#00C896",
        wickDownColor: "#FF4D6A",
      });

      chartRef.current = chart;
      seriesRef.current = series;

      // Resize observer
      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const { width, height } = entry.contentRect;
          chart.applyOptions({ width, height });
        }
      });
      resizeObserver.observe(chartContainerRef.current!);

      fetchCandles();

      return () => {
        resizeObserver.disconnect();
        chart.remove();
      };
    };

    const cleanup = initChart();
    return () => {
      cleanup.then((fn) => fn?.());
    };
  }, []); // Only init once

  // Refetch when pair or timeframe changes
  useEffect(() => {
    if (chartRef.current && seriesRef.current) {
      // Remove all extra series (trade markers) before refetch
      // The candlestick series stays
      fetchCandles();
    }
  }, [selectedPair, selectedTf, fetchCandles]);

  return (
    <motion.div
      className="glass p-5"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <BarChart3 size={16} style={{ color: "var(--color-accent)" }} />
          <h3 className="text-card-title" style={{ color: "var(--color-text-primary)" }}>
            Price Chart
          </h3>
          {lastPrice !== null && (
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
                {lastPrice.toFixed(selectedPair.includes("JPY") || selectedPair.includes("XAU") ? 3 : 5)}
              </span>
              <span
                className="text-[11px] font-mono font-bold"
                style={{ color: priceChange >= 0 ? "var(--color-profit)" : "var(--color-loss)" }}
              >
                {priceChange >= 0 ? "+" : ""}{priceChange.toFixed(3)}%
              </span>
            </div>
          )}
        </div>

        <button
          onClick={fetchCandles}
          className="w-7 h-7 flex items-center justify-center rounded"
          style={{ backgroundColor: "var(--color-bg-elevated)", color: "var(--color-text-secondary)" }}
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Pair + Timeframe selectors */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        {/* Pair selector */}
        <div className="flex items-center gap-1">
          {PAIRS.map((p) => (
            <button
              key={p}
              onClick={() => setSelectedPair(p)}
              className="px-2 py-1 rounded text-[10px] font-mono font-medium transition-colors"
              style={{
                backgroundColor: p === selectedPair ? "var(--color-accent)" : "var(--color-bg-elevated)",
                color: p === selectedPair ? "#fff" : "var(--color-text-secondary)",
              }}
            >
              {formatPair(p)}
            </button>
          ))}
        </div>

        <div className="w-px h-4" style={{ backgroundColor: "var(--color-border)" }} />

        {/* Timeframe selector */}
        <div className="flex items-center gap-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf.value}
              onClick={() => setSelectedTf(tf.value)}
              className="px-2 py-1 rounded text-[10px] font-mono font-medium transition-colors"
              style={{
                backgroundColor: tf.value === selectedTf ? "var(--color-brand)" : "var(--color-bg-elevated)",
                color: tf.value === selectedTf ? "#fff" : "var(--color-text-secondary)",
              }}
            >
              {tf.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart container */}
      <div
        ref={chartContainerRef}
        className="w-full rounded-lg overflow-hidden"
        style={{ height: 400 }}
      />

      {/* Loading overlay */}
      {loading && (
        <div className="flex items-center justify-center py-4">
          <RefreshCw size={16} className="animate-spin" style={{ color: "var(--color-text-tertiary)" }} />
          <span className="ml-2 text-xs" style={{ color: "var(--color-text-tertiary)" }}>
            Loading {formatPair(selectedPair)} candles...
          </span>
        </div>
      )}
    </motion.div>
  );
}
