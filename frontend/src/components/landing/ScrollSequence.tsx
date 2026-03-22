"use client";

import { useRef, useEffect, useState, useCallback } from "react";

/**
 * ScrollSequence — Scroll-driven image sequence animation
 *
 * As the user scrolls INSIDE this component, the current frame updates
 * instantly to match scroll position. The scrollable area is INTERNAL
 * to the component — NOT the window/page scroll.
 *
 * Instead of pre-rendered images, we paint procedural frames to canvas
 * showing the Lumitrade terminal assembling: grid → data → signals → trades.
 */

const TOTAL_FRAMES = 120;
const CANVAS_WIDTH = 1200;
const CANVAS_HEIGHT = 700;

// Color tokens matching the FDS dark terminal theme
const COLORS = {
  bg: "#0D1B2A",
  surface: "#111D2E",
  elevated: "#1A2840",
  border: "#1E3050",
  borderAccent: "#2A4070",
  textPrimary: "#E8F0FE",
  textSecondary: "#8A9BC0",
  textTertiary: "#4A5E80",
  accent: "#3D8EFF",
  profit: "#00C896",
  loss: "#FF4D6A",
  warning: "#FFB347",
  gold: "#E67E22",
};

interface FrameData {
  progress: number; // 0-1
  phase: number;    // 0-5
}

function getFrameData(frame: number): FrameData {
  const progress = frame / TOTAL_FRAMES;
  let phase = 0;
  if (progress < 0.15) phase = 0;       // Dark void
  else if (progress < 0.30) phase = 1;  // Grid appears
  else if (progress < 0.50) phase = 2;  // Data streams in
  else if (progress < 0.70) phase = 3;  // Signals fire
  else if (progress < 0.85) phase = 4;  // Trades execute
  else phase = 5;                        // Equity curve rises
  return { progress, phase };
}

function drawFrame(ctx: CanvasRenderingContext2D, frame: number) {
  const { progress, phase } = getFrameData(frame);
  const w = CANVAS_WIDTH;
  const h = CANVAS_HEIGHT;

  // Clear
  ctx.fillStyle = COLORS.bg;
  ctx.fillRect(0, 0, w, h);

  // Phase 0: Dark void with subtle particles
  if (phase >= 0) {
    const particleAlpha = Math.min(progress * 3, 0.3);
    ctx.fillStyle = `rgba(61, 142, 255, ${particleAlpha})`;
    for (let i = 0; i < 30; i++) {
      const x = ((i * 137.508 + frame * 0.5) % w);
      const y = ((i * 89.123 + frame * 0.3) % h);
      ctx.beginPath();
      ctx.arc(x, y, 1.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Phase 1: Grid lines appear
  if (phase >= 1) {
    const gridAlpha = Math.min((progress - 0.15) / 0.15, 1);
    ctx.strokeStyle = `rgba(30, 48, 80, ${gridAlpha * 0.6})`;
    ctx.lineWidth = 0.5;
    // Vertical lines
    for (let x = 80; x < w - 40; x += 60) {
      ctx.beginPath();
      ctx.moveTo(x, 60);
      ctx.lineTo(x, h - 40);
      ctx.stroke();
    }
    // Horizontal lines
    for (let y = 60; y < h - 40; y += 40) {
      ctx.beginPath();
      ctx.moveTo(80, y);
      ctx.lineTo(w - 40, y);
      ctx.stroke();
    }

    // Sidebar outline
    const sidebarAlpha = gridAlpha * 0.8;
    ctx.strokeStyle = `rgba(30, 48, 80, ${sidebarAlpha})`;
    ctx.lineWidth = 1;
    ctx.strokeRect(20, 20, 200, h - 40);

    // Main panel outline
    ctx.strokeRect(240, 20, w - 260, h - 40);

    // LUMITRADE logo
    ctx.fillStyle = `rgba(230, 126, 34, ${gridAlpha})`;
    ctx.font = "bold 16px 'Space Grotesk', sans-serif";
    ctx.fillText("LUMITRADE", 40, 55);
    ctx.fillStyle = `rgba(74, 94, 128, ${gridAlpha})`;
    ctx.font = "10px 'JetBrains Mono', monospace";
    ctx.fillText("v1.0 · Phase 0", 40, 72);

    // Nav items
    const navItems = ["Dashboard", "Signals", "Trades", "Analytics", "Settings"];
    navItems.forEach((item, i) => {
      const alpha = Math.min(gridAlpha, Math.max(0, (progress - 0.18 - i * 0.02) / 0.05));
      const isActive = i === 0;
      if (isActive) {
        ctx.fillStyle = `rgba(26, 40, 64, ${alpha})`;
        ctx.fillRect(28, 90 + i * 36, 184, 30);
        ctx.fillStyle = `rgba(61, 142, 255, ${alpha})`;
        ctx.fillRect(28, 90 + i * 36, 2, 30);
      }
      ctx.fillStyle = isActive
        ? `rgba(232, 240, 254, ${alpha})`
        : `rgba(138, 155, 192, ${alpha})`;
      ctx.font = "13px 'DM Sans', sans-serif";
      ctx.fillText(item, 52, 110 + i * 36);
    });
  }

  // Phase 2: Data streams in — candlestick chart + numbers
  if (phase >= 2) {
    const dataAlpha = Math.min((progress - 0.30) / 0.20, 1);

    // Top panels (Account, Today, Status)
    const panels = [
      { x: 260, w: 250, title: "Account", value: "$312.45" },
      { x: 530, w: 200, title: "Today", value: "+$4.23" },
      { x: 750, w: 200, title: "System Status", value: "" },
    ];
    panels.forEach((p) => {
      ctx.fillStyle = `rgba(17, 29, 46, ${dataAlpha})`;
      ctx.fillRect(p.x, 40, p.w, 100);
      ctx.strokeStyle = `rgba(30, 48, 80, ${dataAlpha})`;
      ctx.strokeRect(p.x, 40, p.w, 100);
      ctx.fillStyle = `rgba(74, 94, 128, ${dataAlpha})`;
      ctx.font = "10px 'DM Sans', sans-serif";
      ctx.fillText(p.title.toUpperCase(), p.x + 16, 62);
      if (p.value) {
        const isPositive = p.value.startsWith("+");
        ctx.fillStyle = isPositive
          ? `rgba(0, 200, 150, ${dataAlpha})`
          : `rgba(232, 240, 254, ${dataAlpha})`;
        ctx.font = "bold 22px 'JetBrains Mono', monospace";
        ctx.fillText(p.value, p.x + 16, 95);
      }
    });

    // Status dots
    const statuses = ["AI Brain", "Data Feed", "OANDA", "Risk Engine"];
    statuses.forEach((s, i) => {
      const dotAlpha = Math.min(dataAlpha, Math.max(0, (progress - 0.33 - i * 0.03) / 0.05));
      ctx.fillStyle = `rgba(0, 200, 150, ${dotAlpha})`;
      ctx.beginPath();
      ctx.arc(766, 60 + i * 20, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = `rgba(138, 155, 192, ${dotAlpha})`;
      ctx.font = "11px 'DM Sans', sans-serif";
      ctx.fillText(s, 778, 64 + i * 20);
    });

    // Candlestick chart area
    const chartX = 260;
    const chartY = 160;
    const chartW = 500;
    const chartH = 250;
    ctx.fillStyle = `rgba(17, 29, 46, ${dataAlpha})`;
    ctx.fillRect(chartX, chartY, chartW, chartH);
    ctx.strokeStyle = `rgba(30, 48, 80, ${dataAlpha})`;
    ctx.strokeRect(chartX, chartY, chartW, chartH);

    // Draw candlesticks
    const candleCount = Math.floor(dataAlpha * 30);
    for (let i = 0; i < candleCount; i++) {
      const cx = chartX + 20 + i * 16;
      const baseY = chartY + 60 + Math.sin(i * 0.5 + frame * 0.02) * 40;
      const bodyH = 10 + Math.sin(i * 0.7) * 8;
      const isGreen = Math.sin(i * 0.4 + 1) > 0;

      ctx.strokeStyle = isGreen
        ? `rgba(0, 200, 150, ${dataAlpha * 0.7})`
        : `rgba(255, 77, 106, ${dataAlpha * 0.7})`;
      ctx.beginPath();
      ctx.moveTo(cx, baseY - 15);
      ctx.lineTo(cx, baseY + bodyH + 15);
      ctx.stroke();

      ctx.fillStyle = isGreen
        ? `rgba(0, 200, 150, ${dataAlpha * 0.8})`
        : `rgba(255, 77, 106, ${dataAlpha * 0.8})`;
      ctx.fillRect(cx - 4, baseY, 8, bodyH);
    }
  }

  // Phase 3: Signal fires — signal card appears with confidence bar
  if (phase >= 3) {
    const signalAlpha = Math.min((progress - 0.50) / 0.15, 1);

    // Signal card
    const sx = 780;
    const sy = 160;
    ctx.fillStyle = `rgba(17, 29, 46, ${signalAlpha})`;
    ctx.fillRect(sx, sy, 360, 180);
    ctx.strokeStyle = `rgba(0, 200, 150, ${signalAlpha})`;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(sx, sy + 180);
    ctx.stroke();
    ctx.lineWidth = 1;
    ctx.strokeStyle = `rgba(30, 48, 80, ${signalAlpha})`;
    ctx.strokeRect(sx, sy, 360, 180);

    // Signal content
    ctx.fillStyle = `rgba(232, 240, 254, ${signalAlpha})`;
    ctx.font = "bold 14px 'JetBrains Mono', monospace";
    ctx.fillText("EUR/USD", sx + 16, sy + 28);

    // BUY badge
    ctx.fillStyle = `rgba(0, 200, 150, ${signalAlpha * 0.15})`;
    ctx.fillRect(sx + 100, sy + 14, 40, 20);
    ctx.fillStyle = `rgba(0, 200, 150, ${signalAlpha})`;
    ctx.font = "bold 10px 'DM Sans', sans-serif";
    ctx.fillText("BUY", sx + 108, sy + 28);

    // Confidence bar
    const confBarW = 320 * signalAlpha * 0.82;
    ctx.fillStyle = `rgba(26, 40, 64, ${signalAlpha})`;
    ctx.fillRect(sx + 16, sy + 44, 320, 6);
    ctx.fillStyle = `rgba(0, 200, 150, ${signalAlpha})`;
    ctx.fillRect(sx + 16, sy + 44, confBarW, 6);
    ctx.fillStyle = `rgba(138, 155, 192, ${signalAlpha})`;
    ctx.font = "11px 'JetBrains Mono', monospace";
    ctx.fillText("82%", sx + 342, sy + 52);

    // Summary text
    ctx.fillStyle = `rgba(138, 155, 192, ${signalAlpha * 0.9})`;
    ctx.font = "12px 'DM Sans', sans-serif";
    ctx.fillText("EUR/USD shows bullish confluence across", sx + 16, sy + 78);
    ctx.fillText("all timeframes with strong momentum.", sx + 16, sy + 94);

    // Glow effect around signal
    if (signalAlpha > 0.5) {
      const glowAlpha = (signalAlpha - 0.5) * 0.3;
      ctx.shadowColor = `rgba(0, 200, 150, ${glowAlpha})`;
      ctx.shadowBlur = 20;
      ctx.strokeStyle = `rgba(0, 200, 150, ${glowAlpha})`;
      ctx.strokeRect(sx - 1, sy - 1, 362, 182);
      ctx.shadowBlur = 0;
    }
  }

  // Phase 4: Trade executes — order confirmation
  if (phase >= 4) {
    const tradeAlpha = Math.min((progress - 0.70) / 0.10, 1);

    // Execution confirmation overlay
    const ox = 400;
    const oy = 450;
    ctx.fillStyle = `rgba(17, 29, 46, ${tradeAlpha * 0.95})`;
    ctx.fillRect(ox, oy, 360, 80);
    ctx.strokeStyle = `rgba(0, 200, 150, ${tradeAlpha * 0.5})`;
    ctx.strokeRect(ox, oy, 360, 80);

    ctx.fillStyle = `rgba(0, 200, 150, ${tradeAlpha})`;
    ctx.font = "bold 12px 'DM Sans', sans-serif";
    ctx.fillText("✓ TRADE EXECUTED", ox + 16, oy + 26);
    ctx.fillStyle = `rgba(232, 240, 254, ${tradeAlpha})`;
    ctx.font = "11px 'JetBrains Mono', monospace";
    ctx.fillText("EUR/USD BUY  1,000 units @ 1.08430", ox + 16, oy + 48);
    ctx.fillStyle = `rgba(138, 155, 192, ${tradeAlpha})`;
    ctx.fillText("SL: 1.08230  TP: 1.08730  RR: 1.5:1", ox + 16, oy + 66);
  }

  // Phase 5: Equity curve rises
  if (phase >= 5) {
    const eqAlpha = Math.min((progress - 0.85) / 0.15, 1);

    // Equity chart
    const ex = 260;
    const ey = 440;
    const ew = 500;
    const eh = 180;
    ctx.fillStyle = `rgba(17, 29, 46, ${eqAlpha})`;
    ctx.fillRect(ex, ey, ew, eh);
    ctx.strokeStyle = `rgba(30, 48, 80, ${eqAlpha})`;
    ctx.strokeRect(ex, ey, ew, eh);

    ctx.fillStyle = `rgba(74, 94, 128, ${eqAlpha})`;
    ctx.font = "10px 'DM Sans', sans-serif";
    ctx.fillText("EQUITY CURVE", ex + 16, ey + 20);

    // Draw rising equity line
    const points: [number, number][] = [];
    const lineProgress = eqAlpha;
    const numPoints = Math.floor(lineProgress * 40);
    for (let i = 0; i <= numPoints; i++) {
      const px = ex + 30 + (i / 40) * (ew - 60);
      const trend = (i / 40) * 60;
      const noise = Math.sin(i * 0.8) * 12 + Math.sin(i * 0.3) * 8;
      const py = ey + eh - 30 - trend - noise;
      points.push([px, py]);
    }

    if (points.length > 1) {
      // Fill under curve
      ctx.beginPath();
      ctx.moveTo(points[0][0], ey + eh - 10);
      points.forEach(([px, py]) => ctx.lineTo(px, py));
      ctx.lineTo(points[points.length - 1][0], ey + eh - 10);
      ctx.closePath();
      const grad = ctx.createLinearGradient(0, ey, 0, ey + eh);
      grad.addColorStop(0, `rgba(0, 200, 150, ${eqAlpha * 0.2})`);
      grad.addColorStop(1, `rgba(0, 200, 150, 0)`);
      ctx.fillStyle = grad;
      ctx.fill();

      // Stroke the line
      ctx.beginPath();
      ctx.moveTo(points[0][0], points[0][1]);
      points.forEach(([px, py]) => ctx.lineTo(px, py));
      ctx.strokeStyle = `rgba(0, 200, 150, ${eqAlpha})`;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.lineWidth = 1;
    }

    // Final P&L
    ctx.fillStyle = `rgba(0, 200, 150, ${eqAlpha})`;
    ctx.font = "bold 18px 'JetBrains Mono', monospace";
    ctx.fillText("+$47.82", ex + ew - 100, ey + 24);
  }

  // Scroll progress indicator (right edge)
  const indicatorH = h - 80;
  const filledH = indicatorH * progress;
  ctx.fillStyle = `rgba(30, 48, 80, 0.3)`;
  ctx.fillRect(w - 8, 40, 3, indicatorH);
  ctx.fillStyle = COLORS.accent;
  ctx.fillRect(w - 8, 40, 3, filledH);
}

export default function ScrollSequence() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [currentFrame, setCurrentFrame] = useState(0);

  // Paint canvas on frame change
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Handle DPI scaling
    const dpr = window.devicePixelRatio || 1;
    canvas.width = CANVAS_WIDTH * dpr;
    canvas.height = CANVAS_HEIGHT * dpr;
    canvas.style.width = `${CANVAS_WIDTH}px`;
    canvas.style.height = `${CANVAS_HEIGHT}px`;
    ctx.scale(dpr, dpr);

    drawFrame(ctx, currentFrame);
  }, [currentFrame]);

  // Map scroll position to frame
  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const scrollFraction =
      container.scrollTop / (container.scrollHeight - container.clientHeight);
    const frame = Math.min(
      TOTAL_FRAMES,
      Math.max(0, Math.round(scrollFraction * TOTAL_FRAMES))
    );
    setCurrentFrame(frame);
  }, []);

  return (
    <div className="relative w-full flex justify-center">
      {/* Internal scrollable container */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="relative overflow-y-scroll scrollbar-hide"
        style={{
          width: CANVAS_WIDTH,
          height: CANVAS_HEIGHT,
        }}
      >
        {/* Tall spacer to create scroll range */}
        <div style={{ height: CANVAS_HEIGHT * 5, pointerEvents: "none" }} />

        {/* Fixed canvas overlay */}
        <canvas
          ref={canvasRef}
          className="sticky top-0 left-0 block"
          style={{
            width: CANVAS_WIDTH,
            height: CANVAS_HEIGHT,
          }}
        />
      </div>

      {/* Scroll hint */}
      {currentFrame === 0 && (
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
          <div className="flex flex-col items-center gap-1 text-tertiary text-xs">
            <span>Scroll to explore</span>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 3v10M4 9l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
        </div>
      )}
    </div>
  );
}
