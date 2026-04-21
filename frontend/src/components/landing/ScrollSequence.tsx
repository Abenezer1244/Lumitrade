"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { motion, useReducedMotion } from "motion/react";

/**
 * ScrollSequence — Premium scroll-driven procedural terminal animation.
 *
 * Internal scrollable container drives a canvas rendering 120 frames of
 * the Lumitrade terminal assembling from void to a fully operational state.
 * Uses rounded rectangles, gradient fills, glow/bloom effects, and
 * smooth alpha transitions for Apple-level visual quality.
 */

const TOTAL_FRAMES = 120;
const CANVAS_WIDTH = 1280;
const CANVAS_HEIGHT = 720;

const C = {
  bg: "#0D1B2A",
  surface: "#111D2E",
  elevated: "#162636",
  border: "#1E3A5F",
  borderAccent: "#2A4A6F",
  textPrimary: "#E8F0FE",
  textSecondary: "#8A9BC0",
  textTertiary: "#6B7280",
  accent: "#3D8EFF",
  profit: "#00C896",
  loss: "#FF4D6A",
  warning: "#FFB347",
  gold: "#00C896",
};

// ── Helpers ──────────────────────────────────────────────────

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

/** Eased alpha — ease-in-out between two progress thresholds */
function easedAlpha(progress: number, start: number, end: number): number {
  if (progress <= start) return 0;
  if (progress >= end) return 1;
  const t = (progress - start) / (end - start);
  // Smooth-step ease-in-out
  return t * t * (3 - 2 * t);
}

/** Draw a rounded rectangle (no native roundRect in all browsers) */
function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + w - radius, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
  ctx.lineTo(x + w, y + h - radius);
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
  ctx.lineTo(x + radius, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

/** Fill a rounded rectangle */
function fillRoundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
  fillStyle: string | CanvasGradient
) {
  ctx.save();
  roundRect(ctx, x, y, w, h, r);
  ctx.fillStyle = fillStyle;
  ctx.fill();
  ctx.restore();
}

/** Stroke a rounded rectangle */
function strokeRoundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
  strokeStyle: string,
  lineWidth: number = 1
) {
  ctx.save();
  roundRect(ctx, x, y, w, h, r);
  ctx.strokeStyle = strokeStyle;
  ctx.lineWidth = lineWidth;
  ctx.stroke();
  ctx.restore();
}

/** Draw a panel with gradient fill and border */
function drawPanel(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  alpha: number,
  options?: { glow?: string; borderColor?: string }
) {
  const grad = ctx.createLinearGradient(x, y, x, y + h);
  grad.addColorStop(0, hexToRgba(C.surface, alpha * 0.95));
  grad.addColorStop(1, hexToRgba(C.surface, alpha * 0.7));
  fillRoundRect(ctx, x, y, w, h, 8, grad);
  strokeRoundRect(
    ctx, x, y, w, h, 8,
    hexToRgba(options?.borderColor || C.border, alpha * 0.8)
  );

  if (options?.glow) {
    ctx.save();
    ctx.shadowColor = hexToRgba(options.glow, alpha * 0.25);
    ctx.shadowBlur = 24;
    strokeRoundRect(ctx, x, y, w, h, 8, hexToRgba(options.glow, alpha * 0.15), 1.5);
    ctx.restore();
  }
}

// ── Scan-line effect ────────────────────────────────────────

function drawScanLine(
  ctx: CanvasRenderingContext2D,
  progress: number,
  x: number,
  y: number,
  w: number,
  h: number,
  alpha: number
) {
  if (alpha <= 0) return;
  const scanY = y + (progress % 1) * h;
  const grad = ctx.createLinearGradient(x, scanY - 20, x, scanY + 20);
  grad.addColorStop(0, "rgba(61,142,255,0)");
  grad.addColorStop(0.5, hexToRgba(C.accent, alpha * 0.08));
  grad.addColorStop(1, "rgba(61,142,255,0)");
  ctx.fillStyle = grad;
  ctx.fillRect(x, scanY - 20, w, 40);
}

// ── Phase 0: Floating particles + grid emergence ────────────

function drawPhase0(ctx: CanvasRenderingContext2D, progress: number, frame: number) {
  const w = CANVAS_WIDTH;
  const h = CANVAS_HEIGHT;

  // Floating particles
  const particleAlpha = Math.min(progress * 4, 0.4);
  for (let i = 0; i < 50; i++) {
    const seed = i * 137.508;
    const x = ((seed + frame * 0.3) % w);
    const y = ((i * 89.123 + frame * 0.2) % h);
    const size = 1 + (i % 3) * 0.5;
    const flicker = 0.5 + 0.5 * Math.sin(frame * 0.05 + i);
    const alpha = particleAlpha * flicker;

    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.fillStyle = hexToRgba(C.accent, alpha);
    ctx.fill();
  }

  // Subtle grid emergence (starting at 8%)
  const gridAlpha = easedAlpha(progress, 0.08, 0.18) * 0.3;
  if (gridAlpha > 0) {
    ctx.strokeStyle = hexToRgba(C.border, gridAlpha);
    ctx.lineWidth = 0.5;
    for (let x = 80; x < w - 40; x += 60) {
      ctx.beginPath();
      ctx.moveTo(x, 60);
      ctx.lineTo(x, h - 40);
      ctx.stroke();
    }
    for (let y = 60; y < h - 40; y += 40) {
      ctx.beginPath();
      ctx.moveTo(80, y);
      ctx.lineTo(w - 40, y);
      ctx.stroke();
    }
  }
}

// ── Phase 1: Terminal chrome ────────────────────────────────

function drawPhase1(ctx: CanvasRenderingContext2D, progress: number, frame: number) {
  const h = CANVAS_HEIGHT;
  const alpha = easedAlpha(progress, 0.15, 0.30);
  if (alpha <= 0) return;

  // Sidebar panel
  const sidebarGrad = ctx.createLinearGradient(20, 20, 20, h - 20);
  sidebarGrad.addColorStop(0, hexToRgba(C.surface, alpha * 0.9));
  sidebarGrad.addColorStop(1, hexToRgba("#0A1628", alpha * 0.7));
  fillRoundRect(ctx, 20, 20, 210, h - 40, 10, sidebarGrad);
  strokeRoundRect(ctx, 20, 20, 210, h - 40, 10, hexToRgba(C.border, alpha * 0.7));

  // Main area outline
  strokeRoundRect(ctx, 248, 20, CANVAS_WIDTH - 268, h - 40, 10, hexToRgba(C.border, alpha * 0.5));

  // LUMITRADE logo
  const logoAlpha = easedAlpha(progress, 0.16, 0.22);
  ctx.save();
  ctx.font = "bold 17px Satoshi, system-ui, sans-serif";
  ctx.fillStyle = hexToRgba(C.gold, logoAlpha);
  ctx.fillText("LUMITRADE", 42, 56);
  ctx.font = "10px 'JetBrains Mono', monospace";
  ctx.fillStyle = hexToRgba(C.textTertiary, logoAlpha);
  ctx.fillText("v1.0  Phase 0", 42, 72);
  ctx.restore();

  // Separator line under logo
  ctx.strokeStyle = hexToRgba(C.border, alpha * 0.5);
  ctx.lineWidth = 0.5;
  ctx.beginPath();
  ctx.moveTo(38, 84);
  ctx.lineTo(212, 84);
  ctx.stroke();

  // Navigation items with staggered reveal
  const navItems = [
    { name: "Dashboard", active: true },
    { name: "Signals", active: false },
    { name: "Trades", active: false },
    { name: "Analytics", active: false },
    { name: "Settings", active: false },
  ];

  navItems.forEach((item, i) => {
    const itemAlpha = easedAlpha(progress, 0.18 + i * 0.02, 0.24 + i * 0.02);
    if (itemAlpha <= 0) return;

    const iy = 96 + i * 40;

    if (item.active) {
      // Active item background
      fillRoundRect(ctx, 30, iy, 190, 34, 6, hexToRgba(C.elevated, itemAlpha * 0.8));
      // Active indicator bar
      fillRoundRect(ctx, 30, iy + 4, 3, 26, 2, hexToRgba(C.accent, itemAlpha));
      ctx.fillStyle = hexToRgba(C.textPrimary, itemAlpha);
    } else {
      ctx.fillStyle = hexToRgba(C.textSecondary, itemAlpha * 0.7);
    }

    ctx.font = "500 13px Satoshi, system-ui, sans-serif";
    ctx.fillText(item.name, 52, iy + 22);
  });

  // Bottom sidebar section — system label
  const bottomAlpha = easedAlpha(progress, 0.25, 0.30);
  if (bottomAlpha > 0) {
    ctx.font = "500 9px Satoshi, system-ui, sans-serif";
    ctx.fillStyle = hexToRgba(C.textTertiary, bottomAlpha);
    ctx.fillText("SYSTEM", 42, h - 70);
    ctx.fillStyle = hexToRgba(C.textSecondary, bottomAlpha * 0.6);
    ctx.font = "11px Satoshi, system-ui, sans-serif";
    ctx.fillText("Kill Switch", 42, h - 52);
  }

  // Scan-line sweep across sidebar
  drawScanLine(ctx, progress * 3, 20, 20, 210, h - 40, alpha * 0.5);
}

// ── Phase 2: Data flows in ──────────────────────────────────

function drawPhase2(ctx: CanvasRenderingContext2D, progress: number, frame: number) {
  const alpha = easedAlpha(progress, 0.30, 0.50);
  if (alpha <= 0) return;

  // Top stat panels
  const panels = [
    { x: 268, w: 240, title: "ACCOUNT BALANCE", value: "$312.45", color: C.textPrimary },
    { x: 524, w: 200, title: "TODAY P&L", value: "+$4.23", color: C.profit },
    { x: 740, w: 200, title: "OPEN POSITIONS", value: "1", color: C.accent },
    { x: 956, w: 280, title: "SYSTEM STATUS", value: "", color: "" },
  ];

  panels.forEach((p, i) => {
    const panelAlpha = easedAlpha(progress, 0.31 + i * 0.03, 0.40 + i * 0.03);
    if (panelAlpha <= 0) return;

    drawPanel(ctx, p.x, 36, p.w, 100, panelAlpha);

    // Title label
    ctx.font = "500 10px Satoshi, system-ui, sans-serif";
    ctx.fillStyle = hexToRgba(C.textTertiary, panelAlpha);
    ctx.fillText(p.title, p.x + 16, 58);

    if (p.value) {
      ctx.font = "600 24px 'JetBrains Mono', monospace";
      ctx.fillStyle = hexToRgba(p.color, panelAlpha);
      ctx.fillText(p.value, p.x + 16, 98);
    }
  });

  // Status dots inside system status panel
  const statuses = [
    { name: "AI Brain", ok: true },
    { name: "Data Feed", ok: true },
    { name: "OANDA", ok: true },
    { name: "Risk Engine", ok: true },
  ];
  statuses.forEach((s, i) => {
    const dotAlpha = easedAlpha(progress, 0.37 + i * 0.025, 0.43 + i * 0.025);
    if (dotAlpha <= 0) return;

    const dx = 972;
    const dy = 62 + i * 20;

    // Green dot
    ctx.beginPath();
    ctx.arc(dx, dy, 4, 0, Math.PI * 2);
    ctx.fillStyle = hexToRgba(C.profit, dotAlpha);
    ctx.fill();

    // Glow around dot
    ctx.beginPath();
    ctx.arc(dx, dy, 6, 0, Math.PI * 2);
    ctx.fillStyle = hexToRgba(C.profit, dotAlpha * 0.15);
    ctx.fill();

    ctx.font = "11px Satoshi, system-ui, sans-serif";
    ctx.fillStyle = hexToRgba(C.textSecondary, dotAlpha);
    ctx.fillText(s.name, dx + 12, dy + 4);
  });

  // ── Candlestick chart panel ──
  const chartX = 268;
  const chartY = 152;
  const chartW = 520;
  const chartH = 280;
  const chartAlpha = easedAlpha(progress, 0.34, 0.48);

  if (chartAlpha > 0) {
    drawPanel(ctx, chartX, chartY, chartW, chartH, chartAlpha);

    // Chart title
    ctx.font = "500 10px Satoshi, system-ui, sans-serif";
    ctx.fillStyle = hexToRgba(C.textTertiary, chartAlpha);
    ctx.fillText("EUR/USD  H1", chartX + 16, chartY + 22);
    ctx.font = "12px 'JetBrains Mono', monospace";
    ctx.fillStyle = hexToRgba(C.textSecondary, chartAlpha);
    ctx.fillText("1.08430", chartX + chartW - 80, chartY + 22);

    // Price axis labels
    const priceBase = 1.082;
    for (let i = 0; i < 5; i++) {
      const py = chartY + 50 + i * 50;
      const price = (priceBase + (4 - i) * 0.001).toFixed(4);
      ctx.font = "9px 'JetBrains Mono', monospace";
      ctx.fillStyle = hexToRgba(C.textTertiary, chartAlpha * 0.6);
      ctx.fillText(price, chartX + chartW - 60, py);

      // Horizontal grid line
      ctx.strokeStyle = hexToRgba(C.border, chartAlpha * 0.3);
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(chartX + 14, py - 4);
      ctx.lineTo(chartX + chartW - 66, py - 4);
      ctx.stroke();
    }

    // Draw candlesticks with staggered appearance
    const candleCount = Math.floor(chartAlpha * 32);
    for (let i = 0; i < candleCount; i++) {
      const cx = chartX + 28 + i * 15;
      if (cx > chartX + chartW - 70) break;

      const baseY = chartY + 100 + Math.sin(i * 0.45 + 2) * 50 + Math.sin(i * 0.15) * 20;
      const bodyH = 8 + Math.abs(Math.sin(i * 0.7)) * 14;
      const isGreen = Math.sin(i * 0.4 + 1) > 0;
      const candleColor = isGreen ? C.profit : C.loss;

      // Wick
      ctx.strokeStyle = hexToRgba(candleColor, chartAlpha * 0.6);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx, baseY - 12);
      ctx.lineTo(cx, baseY + bodyH + 12);
      ctx.stroke();

      // Body — rounded
      fillRoundRect(
        ctx,
        cx - 4, baseY, 8, bodyH, 2,
        hexToRgba(candleColor, chartAlpha * 0.85)
      );
    }

    // Scan line across chart
    drawScanLine(ctx, progress * 2.5, chartX, chartY, chartW, chartH, chartAlpha * 0.4);
  }

  // ── Positions table panel ──
  const tableX = 268;
  const tableY = 448;
  const tableW = 520;
  const tableH = 240;
  const tableAlpha = easedAlpha(progress, 0.40, 0.50);

  if (tableAlpha > 0) {
    drawPanel(ctx, tableX, tableY, tableW, tableH, tableAlpha);
    ctx.font = "500 10px Satoshi, system-ui, sans-serif";
    ctx.fillStyle = hexToRgba(C.textTertiary, tableAlpha);
    ctx.fillText("RECENT SIGNALS", tableX + 16, tableY + 22);

    // Table header
    const headers = ["Pair", "Dir", "Conf", "Time", "Status"];
    const colX = [tableX + 16, tableX + 100, tableX + 160, tableX + 240, tableX + 340];
    headers.forEach((h, i) => {
      ctx.font = "500 9px Satoshi, system-ui, sans-serif";
      ctx.fillStyle = hexToRgba(C.textTertiary, tableAlpha * 0.7);
      ctx.fillText(h, colX[i], tableY + 44);
    });

    // Separator
    ctx.strokeStyle = hexToRgba(C.border, tableAlpha * 0.4);
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(tableX + 12, tableY + 50);
    ctx.lineTo(tableX + tableW - 12, tableY + 50);
    ctx.stroke();

    // Empty state rows (skeleton-like)
    for (let r = 0; r < 4; r++) {
      const ry = tableY + 60 + r * 30;
      const rowAlpha = tableAlpha * 0.25;
      fillRoundRect(ctx, colX[0], ry, 60, 12, 3, hexToRgba(C.border, rowAlpha));
      fillRoundRect(ctx, colX[1], ry, 30, 12, 3, hexToRgba(C.border, rowAlpha));
      fillRoundRect(ctx, colX[2], ry, 50, 12, 3, hexToRgba(C.border, rowAlpha));
      fillRoundRect(ctx, colX[3], ry, 60, 12, 3, hexToRgba(C.border, rowAlpha));
      fillRoundRect(ctx, colX[4], ry, 50, 12, 3, hexToRgba(C.border, rowAlpha));
    }
  }
}

// ── Phase 3: AI signal fires ────────────────────────────────

function drawPhase3(ctx: CanvasRenderingContext2D, progress: number, frame: number) {
  const alpha = easedAlpha(progress, 0.50, 0.68);
  if (alpha <= 0) return;

  const sx = 808;
  const sy = 152;
  const sw = 420;
  const sh = 340;

  // Signal panel with profit-green glow
  drawPanel(ctx, sx, sy, sw, sh, alpha, { glow: C.profit, borderColor: C.profit });

  // Left accent bar
  fillRoundRect(ctx, sx + 2, sy + 8, 3, sh - 16, 2, hexToRgba(C.profit, alpha));

  // Pair name
  ctx.font = "600 16px 'JetBrains Mono', monospace";
  ctx.fillStyle = hexToRgba(C.textPrimary, alpha);
  ctx.fillText("EUR/USD", sx + 20, sy + 32);

  // BUY badge
  const buyAlpha = easedAlpha(progress, 0.52, 0.56);
  fillRoundRect(ctx, sx + 120, sy + 16, 44, 22, 4, hexToRgba(C.profit, buyAlpha * 0.15));
  strokeRoundRect(ctx, sx + 120, sy + 16, 44, 22, 4, hexToRgba(C.profit, buyAlpha * 0.3));
  ctx.font = "600 10px Satoshi, system-ui, sans-serif";
  ctx.fillStyle = hexToRgba(C.profit, buyAlpha);
  ctx.fillText("BUY", sx + 130, sy + 31);

  // Timeframe badge
  fillRoundRect(ctx, sx + 174, sy + 16, 32, 22, 4, hexToRgba(C.accent, buyAlpha * 0.1));
  ctx.font = "500 10px 'JetBrains Mono', monospace";
  ctx.fillStyle = hexToRgba(C.accent, buyAlpha * 0.8);
  ctx.fillText("H1", sx + 182, sy + 31);

  // Confidence bar
  const confAlpha = easedAlpha(progress, 0.54, 0.60);
  const confBarW = 380;
  const confFill = confBarW * confAlpha * 0.82;

  ctx.font = "500 10px Satoshi, system-ui, sans-serif";
  ctx.fillStyle = hexToRgba(C.textTertiary, confAlpha);
  ctx.fillText("CONFIDENCE", sx + 20, sy + 60);

  fillRoundRect(ctx, sx + 20, sy + 66, confBarW, 6, 3, hexToRgba(C.elevated, confAlpha));
  if (confFill > 0) {
    const barGrad = ctx.createLinearGradient(sx + 20, 0, sx + 20 + confFill, 0);
    barGrad.addColorStop(0, hexToRgba(C.profit, confAlpha * 0.8));
    barGrad.addColorStop(1, hexToRgba(C.profit, confAlpha));
    fillRoundRect(ctx, sx + 20, sy + 66, confFill, 6, 3, barGrad);
  }
  ctx.font = "600 11px 'JetBrains Mono', monospace";
  ctx.fillStyle = hexToRgba(C.profit, confAlpha);
  ctx.fillText("82%", sx + confBarW - 4, sy + 60);

  // Price levels
  const priceAlpha = easedAlpha(progress, 0.56, 0.64);
  const priceBoxes = [
    { label: "ENTRY", value: "1.08430", color: C.textPrimary },
    { label: "SL", value: "1.08230", color: C.loss },
    { label: "TP", value: "1.08730", color: C.profit },
  ];
  priceBoxes.forEach((p, i) => {
    const bx = sx + 20 + i * 130;
    const by = sy + 86;
    fillRoundRect(ctx, bx, by, 118, 48, 6, hexToRgba(C.bg, priceAlpha * 0.6));
    strokeRoundRect(ctx, bx, by, 118, 48, 6, hexToRgba(C.border, priceAlpha * 0.4));

    ctx.font = "500 9px Satoshi, system-ui, sans-serif";
    ctx.fillStyle = hexToRgba(C.textTertiary, priceAlpha);
    ctx.fillText(p.label, bx + 10, by + 18);
    ctx.font = "500 14px 'JetBrains Mono', monospace";
    ctx.fillStyle = hexToRgba(p.color, priceAlpha);
    ctx.fillText(p.value, bx + 10, by + 38);
  });

  // RR ratio badge
  fillRoundRect(ctx, sx + 20, sy + 146, 60, 24, 4, hexToRgba(C.accent, priceAlpha * 0.1));
  ctx.font = "600 10px 'JetBrains Mono', monospace";
  ctx.fillStyle = hexToRgba(C.accent, priceAlpha);
  ctx.fillText("RR 1.5:1", sx + 28, sy + 162);

  // AI Reasoning section
  const reasonAlpha = easedAlpha(progress, 0.60, 0.68);
  if (reasonAlpha > 0) {
    ctx.strokeStyle = hexToRgba(C.border, reasonAlpha * 0.4);
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(sx + 16, sy + 182);
    ctx.lineTo(sx + sw - 16, sy + 182);
    ctx.stroke();

    ctx.font = "500 9px Satoshi, system-ui, sans-serif";
    ctx.fillStyle = hexToRgba(C.textTertiary, reasonAlpha);
    ctx.fillText("AI REASONING", sx + 20, sy + 200);

    ctx.font = "12px 'JetBrains Mono', monospace";
    ctx.fillStyle = hexToRgba(C.textSecondary, reasonAlpha * 0.85);
    const lines = [
      "EUR/USD shows bullish confluence across",
      "H4, H1, and M15. RSI turning up from 42,",
      "MACD histogram positive. EMA alignment",
      "supports continued upside momentum.",
    ];
    lines.forEach((line, i) => {
      const lineAlpha = easedAlpha(progress, 0.61 + i * 0.015, 0.65 + i * 0.015);
      ctx.fillStyle = hexToRgba(C.textSecondary, lineAlpha * 0.85);
      ctx.fillText(line, sx + 20, sy + 220 + i * 18);
    });

    // Timeframe score bars
    const tfAlpha = easedAlpha(progress, 0.64, 0.68);
    const tfs = [
      { label: "H4", score: 0.9, color: C.profit },
      { label: "H1", score: 0.78, color: C.profit },
      { label: "M15", score: 0.65, color: C.warning },
    ];
    tfs.forEach((tf, i) => {
      const tx = sx + 20 + i * 130;
      const ty = sy + 302;
      ctx.font = "500 9px 'JetBrains Mono', monospace";
      ctx.fillStyle = hexToRgba(C.textTertiary, tfAlpha);
      ctx.fillText(tf.label, tx, ty);
      fillRoundRect(ctx, tx + 28, ty - 8, 90, 6, 3, hexToRgba(C.elevated, tfAlpha));
      fillRoundRect(ctx, tx + 28, ty - 8, 90 * tf.score * tfAlpha, 6, 3, hexToRgba(tf.color, tfAlpha));
    });
  }
}

// ── Phase 4: Trade executes ─────────────────────────────────

function drawPhase4(ctx: CanvasRenderingContext2D, progress: number, frame: number) {
  const alpha = easedAlpha(progress, 0.70, 0.84);
  if (alpha <= 0) return;

  // Execution confirmation panel (centered in chart area)
  const ox = 350;
  const oy = 460;
  const ow = 360;
  const oh = 100;

  drawPanel(ctx, ox, oy, ow, oh, alpha, { glow: C.profit });

  // Checkmark circle
  const checkAlpha = easedAlpha(progress, 0.72, 0.78);
  ctx.save();
  ctx.beginPath();
  ctx.arc(ox + 28, oy + 34, 14, 0, Math.PI * 2);
  ctx.fillStyle = hexToRgba(C.profit, checkAlpha * 0.15);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(ox + 28, oy + 34, 14, 0, Math.PI * 2);
  ctx.strokeStyle = hexToRgba(C.profit, checkAlpha * 0.6);
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Checkmark
  if (checkAlpha > 0.3) {
    ctx.beginPath();
    ctx.moveTo(ox + 21, oy + 34);
    ctx.lineTo(ox + 26, oy + 39);
    ctx.lineTo(ox + 36, oy + 28);
    ctx.strokeStyle = hexToRgba(C.profit, checkAlpha);
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.stroke();
  }
  ctx.restore();

  // Text
  ctx.font = "600 12px Satoshi, system-ui, sans-serif";
  ctx.fillStyle = hexToRgba(C.profit, alpha);
  ctx.fillText("TRADE EXECUTED", ox + 52, oy + 30);

  ctx.font = "11px 'JetBrains Mono', monospace";
  ctx.fillStyle = hexToRgba(C.textPrimary, alpha);
  ctx.fillText("EUR/USD  BUY  1,000 units @ 1.08430", ox + 52, oy + 50);

  ctx.font = "11px 'JetBrains Mono', monospace";
  ctx.fillStyle = hexToRgba(C.textSecondary, alpha * 0.8);
  ctx.fillText("SL: 1.08230   TP: 1.08730   RR: 1.5:1", ox + 52, oy + 70);

  // Now populate the signals table with a real row
  const tableAlpha = easedAlpha(progress, 0.75, 0.82);
  if (tableAlpha > 0) {
    const tableX = 268;
    const tableY = 448;
    const colX = [tableX + 16, tableX + 100, tableX + 160, tableX + 240, tableX + 340];
    const ry = tableY + 60;

    ctx.font = "500 11px 'JetBrains Mono', monospace";
    ctx.fillStyle = hexToRgba(C.textPrimary, tableAlpha);
    ctx.fillText("EUR/USD", colX[0], ry + 10);

    // BUY mini-badge
    fillRoundRect(ctx, colX[1], ry, 30, 16, 3, hexToRgba(C.profit, tableAlpha * 0.15));
    ctx.font = "600 8px Satoshi, system-ui, sans-serif";
    ctx.fillStyle = hexToRgba(C.profit, tableAlpha);
    ctx.fillText("BUY", colX[1] + 5, ry + 11);

    // Confidence mini-bar
    fillRoundRect(ctx, colX[2], ry + 3, 60, 4, 2, hexToRgba(C.elevated, tableAlpha));
    fillRoundRect(ctx, colX[2], ry + 3, 49, 4, 2, hexToRgba(C.profit, tableAlpha));
    ctx.font = "9px 'JetBrains Mono', monospace";
    ctx.fillStyle = hexToRgba(C.textSecondary, tableAlpha);
    ctx.fillText("82%", colX[2] + 64, ry + 10);

    // Time
    ctx.font = "10px 'JetBrains Mono', monospace";
    ctx.fillStyle = hexToRgba(C.textTertiary, tableAlpha);
    ctx.fillText("2m ago", colX[3], ry + 10);

    // Status badge
    fillRoundRect(ctx, colX[4], ry, 56, 16, 3, hexToRgba(C.profit, tableAlpha * 0.1));
    ctx.font = "600 8px Satoshi, system-ui, sans-serif";
    ctx.fillStyle = hexToRgba(C.profit, tableAlpha);
    ctx.fillText("FILLED", colX[4] + 8, ry + 11);
  }
}

// ── Phase 5: Equity curve rises ─────────────────────────────

function drawPhase5(ctx: CanvasRenderingContext2D, progress: number, frame: number) {
  const alpha = easedAlpha(progress, 0.85, 1.0);
  if (alpha <= 0) return;

  // Equity chart replaces the signal table area
  const ex = 268;
  const ey = 570;
  const ew = 520;
  const eh = 110;

  drawPanel(ctx, ex, ey, ew, eh, alpha);

  ctx.font = "500 10px Satoshi, system-ui, sans-serif";
  ctx.fillStyle = hexToRgba(C.textTertiary, alpha);
  ctx.fillText("EQUITY CURVE", ex + 16, ey + 18);

  // Build equity line points
  const points: [number, number][] = [];
  const lineProgress = alpha;
  const numPoints = Math.floor(lineProgress * 50);

  for (let i = 0; i <= numPoints; i++) {
    const px = ex + 20 + (i / 50) * (ew - 50);
    const trend = (i / 50) * 50;
    const noise = Math.sin(i * 0.6) * 8 + Math.sin(i * 0.25) * 5;
    const py = ey + eh - 16 - trend - noise;
    points.push([px, Math.max(ey + 24, py)]);
  }

  if (points.length > 1) {
    // Gradient fill under curve
    ctx.beginPath();
    ctx.moveTo(points[0][0], ey + eh - 6);
    points.forEach(([px, py]) => ctx.lineTo(px, py));
    ctx.lineTo(points[points.length - 1][0], ey + eh - 6);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, ey + 20, 0, ey + eh);
    grad.addColorStop(0, hexToRgba(C.profit, alpha * 0.25));
    grad.addColorStop(1, hexToRgba(C.profit, 0));
    ctx.fillStyle = grad;
    ctx.fill();

    // The line itself
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i][0], points[i][1]);
    }
    ctx.strokeStyle = hexToRgba(C.profit, alpha);
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineWidth = 1;

    // Glow dot at the end
    const last = points[points.length - 1];
    ctx.beginPath();
    ctx.arc(last[0], last[1], 4, 0, Math.PI * 2);
    ctx.fillStyle = hexToRgba(C.profit, alpha);
    ctx.fill();
    ctx.save();
    ctx.shadowColor = hexToRgba(C.profit, alpha * 0.5);
    ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.arc(last[0], last[1], 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  // Final P&L
  const pnlAlpha = easedAlpha(progress, 0.92, 1.0);
  ctx.save();
  ctx.font = "700 20px 'JetBrains Mono', monospace";
  ctx.fillStyle = hexToRgba(C.profit, pnlAlpha);
  ctx.shadowColor = hexToRgba(C.profit, pnlAlpha * 0.3);
  ctx.shadowBlur = 16;
  ctx.fillText("+$47.82", ex + ew - 110, ey + 20);
  ctx.restore();

  // "System Online" badge at bottom-right of main area
  const badgeAlpha = easedAlpha(progress, 0.95, 1.0);
  if (badgeAlpha > 0) {
    const bx = 1060;
    const by = 640;
    fillRoundRect(ctx, bx, by, 160, 30, 6, hexToRgba(C.profit, badgeAlpha * 0.08));
    strokeRoundRect(ctx, bx, by, 160, 30, 6, hexToRgba(C.profit, badgeAlpha * 0.3));

    // Pulsing dot
    const pulse = 0.7 + 0.3 * Math.sin(frame * 0.1);
    ctx.beginPath();
    ctx.arc(bx + 16, by + 15, 4, 0, Math.PI * 2);
    ctx.fillStyle = hexToRgba(C.profit, badgeAlpha * pulse);
    ctx.fill();

    ctx.font = "600 11px Satoshi, system-ui, sans-serif";
    ctx.fillStyle = hexToRgba(C.profit, badgeAlpha);
    ctx.fillText("SYSTEM ONLINE", bx + 28, by + 19);
  }
}

// ── Master draw function ────────────────────────────────────

function drawFrame(ctx: CanvasRenderingContext2D, frame: number) {
  const progress = frame / TOTAL_FRAMES;
  const w = CANVAS_WIDTH;
  const h = CANVAS_HEIGHT;

  // Clear to background
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, w, h);

  // Enable anti-aliased text
  ctx.textBaseline = "alphabetic";
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";

  // Draw all phases (they self-gate via easedAlpha)
  drawPhase0(ctx, progress, frame);
  drawPhase1(ctx, progress, frame);
  drawPhase2(ctx, progress, frame);
  drawPhase3(ctx, progress, frame);
  drawPhase4(ctx, progress, frame);
  drawPhase5(ctx, progress, frame);

  // ── Right-edge progress indicator ──
  const indicatorH = h - 80;
  const filledH = indicatorH * progress;
  fillRoundRect(ctx, w - 10, 40, 4, indicatorH, 2, hexToRgba(C.border, 0.3));
  if (filledH > 0) {
    const progGrad = ctx.createLinearGradient(0, 40, 0, 40 + filledH);
    progGrad.addColorStop(0, hexToRgba(C.accent, 0.4));
    progGrad.addColorStop(1, hexToRgba(C.accent, 0.9));
    fillRoundRect(ctx, w - 10, 40, 4, filledH, 2, progGrad);
  }
}

// ── Component ───────────────────────────────────────────────

export default function ScrollSequence() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [currentFrame, setCurrentFrame] = useState(0);
  const rafRef = useRef<number>(0);
  const prefersReducedMotion = useReducedMotion();

  // Paint canvas on frame change
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
    canvas.width = CANVAS_WIDTH * dpr;
    canvas.height = CANVAS_HEIGHT * dpr;
    canvas.style.width = `${CANVAS_WIDTH}px`;
    canvas.style.height = `${CANVAS_HEIGHT}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    drawFrame(ctx, currentFrame);
  }, [currentFrame]);

  // Map scroll position to frame via rAF for smooth performance
  const handleScroll = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);

    rafRef.current = requestAnimationFrame(() => {
      const container = scrollContainerRef.current;
      if (!container) return;
      const maxScroll = container.scrollHeight - container.clientHeight;
      if (maxScroll <= 0) return;
      const scrollFraction = container.scrollTop / maxScroll;
      const frame = Math.min(
        TOTAL_FRAMES,
        Math.max(0, Math.round(scrollFraction * TOTAL_FRAMES))
      );
      setCurrentFrame(frame);
    });
  }, []);

  // If reduced motion, jump to final frame
  useEffect(() => {
    if (prefersReducedMotion) {
      setCurrentFrame(TOTAL_FRAMES);
    }
  }, [prefersReducedMotion]);

  return (
    <div className="relative w-full flex justify-center">
      {/* Internal scrollable container */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="relative overflow-y-scroll scrollbar-hide"
        style={{
          width: "100%",
          maxWidth: CANVAS_WIDTH,
          height: Math.min(CANVAS_HEIGHT, 720),
        }}
      >
        {/* Tall spacer to create scroll range — 6x canvas height */}
        <div style={{ height: CANVAS_HEIGHT * 6, pointerEvents: "none" }} />

        {/* Canvas — sticky so it stays in view while user scrolls the spacer */}
        <canvas
          ref={canvasRef}
          className="sticky top-0 left-0 block w-full"
          style={{
            maxWidth: CANVAS_WIDTH,
            height: "auto",
            aspectRatio: `${CANVAS_WIDTH} / ${CANVAS_HEIGHT}`,
          }}
        />
      </div>

      {/* Scroll hint with animated chevron */}
      {currentFrame < 5 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
          className="absolute bottom-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1.5"
        >
          <span className="text-xs font-medium" style={{ color: "#4A5E80" }}>
            Scroll to explore
          </span>
          <motion.svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            animate={{ y: [0, 6, 0] }}
            transition={{
              duration: 1.8,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          >
            <path
              d="M10 4v12M5 11l5 5 5-5"
              stroke="#4A5E80"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </motion.svg>
        </motion.div>
      )}
    </div>
  );
}
