



LUMITRADE
Frontend Developer Specification

ROLE 4 — SENIOR FRONTEND DEVELOPER
Version 1.0  |  Next.js 14 + TypeScript + Tailwind CSS + Supabase Realtime
Classification: Confidential
Date: March 20, 2026




# 1. Design System & Visual Language
## 1.1 Design Philosophy
Lumitrade's dashboard adopts a premium dark trading terminal aesthetic — authoritative, data-dense, and precise. The visual language draws from professional Bloomberg-style terminals and institutional trading platforms: deep navy backgrounds, sharp accent colors, monospaced data fields, and deliberate use of color to communicate system state at a glance.

Design Principle  Every pixel communicates market state. Green means profit/buy. Red means loss/sell. Amber means warning/caution. Never use these colors decoratively.

## 1.2 Color System

## 1.3 Typography Scale

## 1.4 Spacing & Layout System
- Base unit: 4px. All spacing values are multiples of 4.
- Page max-width: 1440px, centered with 24px side padding on desktop.
- Sidebar: 240px fixed. Main content: fills remaining width.
- Card padding: 20px (p-5). Section gap: 16px (gap-4). Card gap: 12px (gap-3).
- Border radius: 8px cards (rounded-lg), 6px inputs (rounded-md), 4px badges (rounded).

## 1.5 Status Color System
System status is communicated consistently via color across ALL components. These mappings are non-negotiable:

# 2. Application Structure
## 2.1 Next.js App Router Structure
frontend/src/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # Root layout — sidebar + topbar
│   ├── page.tsx                  # Dashboard home (redirect to /dashboard)
│   ├── dashboard/
│   │   └── page.tsx              # Main dashboard overview
│   ├── signals/
│   │   └── page.tsx              # Signal feed + detail panel
│   ├── trades/
│   │   └── page.tsx              # Trade history + filters + export
│   ├── analytics/
│   │   └── page.tsx              # Performance analytics + charts
│   ├── settings/
│   │   └── page.tsx              # System configuration
│   ├── api/                      # Next.js API routes
│   │   ├── account/route.ts      # GET /api/account/summary
│   │   ├── positions/route.ts    # GET /api/positions/open
│   │   ├── signals/route.ts      # GET /api/signals/recent
│   │   ├── trades/route.ts       # GET /api/trades/history
│   │   ├── analytics/route.ts    # GET /api/analytics/summary
│   │   ├── system/
│   │   │   ├── health/route.ts   # GET /api/system/health
│   │   │   └── alerts/route.ts   # GET /api/system/alerts
│   │   ├── control/
│   │   │   └── kill-switch/route.ts  # POST — emergency halt
│   │   └── settings/route.ts     # GET + PUT /api/settings
│   └── auth/
│       ├── login/page.tsx        # Login page
│       └── callback/route.ts     # Supabase auth callback
│
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx           # Navigation sidebar
│   │   ├── TopBar.tsx            # Top bar — system status + account balance
│   │   └── PageContainer.tsx     # Standard page wrapper
│   ├── dashboard/
│   │   ├── AccountPanel.tsx      # Balance, equity, margin
│   │   ├── TodayPanel.tsx        # Today's P&L, trades, win rate
│   │   ├── SystemStatusPanel.tsx # All component health indicators
│   │   ├── OpenPositionsTable.tsx # Live open positions
│   │   └── KillSwitchButton.tsx  # Emergency halt control
│   ├── signals/
│   │   ├── SignalFeed.tsx        # Real-time signal list
│   │   ├── SignalCard.tsx        # Individual signal with expand
│   │   ├── SignalDetailPanel.tsx # Expanded AI reasoning view
│   │   ├── ConfidenceBar.tsx     # Visual confidence indicator
│   │   └── TimeframeScores.tsx   # H4/H1/M15 confluence bars
│   ├── trades/
│   │   ├── TradeHistoryTable.tsx # Paginated trade log
│   │   ├── TradeFilters.tsx      # Date, pair, outcome filters
│   │   └── ExportButton.tsx      # CSV export
│   ├── analytics/
│   │   ├── EquityCurve.tsx       # Recharts line chart
│   │   ├── MetricsGrid.tsx       # Win rate, PF, Sharpe, drawdown
│   │   ├── PairBreakdown.tsx     # Per-pair performance
│   │   └── SessionBreakdown.tsx  # Per-session performance
│   ├── settings/
│   │   ├── RiskSettings.tsx      # Risk % sliders
│   │   ├── TradingSettings.tsx   # Pairs, intervals, thresholds
│   │   └── ModeToggle.tsx        # Paper / Live mode switch
│   └── ui/                       # Shared primitives
│       ├── Badge.tsx             # Status badges
│       ├── StatusDot.tsx         # Online/offline indicators
│       ├── PriceDisplay.tsx      # Formatted price with color
│       ├── PnlDisplay.tsx        # P&L with + / - color
│       ├── LoadingSpinner.tsx
│       ├── EmptyState.tsx
│       └── ConfirmDialog.tsx     # Kill switch confirmation
│
├── hooks/
│   ├── useRealtime.ts            # Supabase Realtime subscription
│   ├── useAccount.ts             # Account data with polling
│   ├── useSignals.ts             # Signal feed with realtime
│   ├── useOpenPositions.ts       # Open positions with realtime
│   ├── useTradeHistory.ts        # Paginated trade history
│   └── useSystemStatus.ts        # System health polling
│
├── lib/
│   ├── supabase.ts               # Supabase client (browser + server)
│   ├── api.ts                    # Typed API client functions
│   └── formatters.ts             # Price, P&L, date formatting
│
└── types/
├── trading.ts                # Trade, Signal, Position TypeScript types
└── system.ts                 # SystemStatus, AccountSummary types

# 3. TypeScript Type Definitions
## 3.1 types/trading.ts
// ── Enums ──────────────────────────────────────────────────────
export type Action = "BUY" | "SELL" | "HOLD";
export type Direction = "BUY" | "SELL";
export type TradingMode = "PAPER" | "LIVE";
export type Outcome = "WIN" | "LOSS" | "BREAKEVEN";
export type Session = "LONDON" | "NEW_YORK" | "OVERLAP" | "TOKYO" | "OTHER";
export type ExitReason = "SL_HIT" | "TP_HIT" | "AI_CLOSE" | "MANUAL" | "EMERGENCY" | "UNKNOWN";
export type GenerationMethod = "AI" | "RULE_BASED";

// ── Signal ─────────────────────────────────────────────────────
export interface Signal {
id: string;
pair: string;
action: Action;
confidence_raw: number;
confidence_adjusted: number;
confidence_adjustment_log: Record<string, number>;
entry_price: string;          // Stored as string for Decimal precision
stop_loss: string;
take_profit: string;
summary: string;
reasoning: string;
timeframe_scores: {
h4: number;
h1: number;
m15: number;
};
indicators_snapshot: IndicatorSnapshot;
key_levels: string[];
news_context: NewsEvent[];
session: Session;
spread_pips: string;
executed: boolean;
rejection_reason: string | null;
generation_method: GenerationMethod;
created_at: string;
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

// ── Trade ──────────────────────────────────────────────────────
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

// ── Open Position (enriched with live P&L) ─────────────────────
export interface OpenPosition extends Trade {
live_pnl_pips: number;    // Computed from current price
live_pnl_usd: number;
current_price: string;
}

## 3.2 types/system.ts
export type RiskState =
| "NORMAL" | "CAUTIOUS" | "NEWS_BLOCK"
| "DAILY_LIMIT" | "WEEKLY_LIMIT"
| "CIRCUIT_OPEN" | "EMERGENCY_HALT";

export type ComponentStatus = "ok" | "degraded" | "offline";

export interface SystemHealth {
status: "healthy" | "degraded" | "offline";
instance_id: string;
is_primary: boolean;
timestamp: string;
uptime_seconds: number;
components: {
oanda_api:      { status: ComponentStatus; latency_ms: number };
ai_brain:       { status: ComponentStatus; last_call_ago_s: number };
database:       { status: ComponentStatus; latency_ms: number };
price_feed:     { status: ComponentStatus; last_tick_ago_s: number };
risk_engine:    { status: ComponentStatus; state: RiskState };
circuit_breaker:{ status: "closed" | "open" | "half_open" };
};
trading: {
mode: "PAPER" | "LIVE";
open_positions: number;
daily_pnl_usd: number;
signals_today: number;
};
}

export interface AccountSummary {
balance: string;
equity: string;
margin_used: string;
margin_available: string;
open_trade_count: number;
daily_pnl_usd: string;
daily_pnl_pct: string;
daily_trade_count: number;
daily_win_count: number;
daily_win_rate: string;
mode: "PAPER" | "LIVE";
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
}

# 4. Key Component Specifications
## 4.1 layout/Sidebar.tsx
The sidebar is the primary navigation element. It is fixed at 240px wide on desktop. It collapses to icon-only at tablet breakpoint. It shows the Lumitrade logo, all navigation items, the trading mode badge, and the system uptime indicator.

// components/layout/Sidebar.tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
LayoutDashboard, Zap, History, BarChart2,
Settings, Activity
} from "lucide-react";
import { useSystemStatus } from "@/hooks/useSystemStatus";
import StatusDot from "@/components/ui/StatusDot";

const NAV_ITEMS = [
{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
{ href: "/signals",   label: "Signals",   icon: Zap           },
{ href: "/trades",    label: "Trades",    icon: History        },
{ href: "/analytics", label: "Analytics", icon: BarChart2      },
{ href: "/settings",  label: "Settings",  icon: Settings       },
];

export default function Sidebar() {
const pathname = usePathname();
const { health } = useSystemStatus();

return (
<aside className="w-60 min-h-screen bg-surface border-r border-border
flex flex-col fixed left-0 top-0 z-30">

{/* Logo */}
<div className="px-5 py-6 border-b border-border">
<span className="font-display text-xl font-semibold text-gold tracking-wide">
LUMITRADE
</span>
<p className="text-tertiary text-xs mt-0.5 font-mono">v1.0 · Phase 0</p>
</div>

{/* Nav */}
<nav className="flex-1 px-3 py-4 space-y-1">
{NAV_ITEMS.map(({ href, label, icon: Icon }) => {
const active = pathname.startsWith(href);
return (
<Link key={href} href={href}
className={`flex items-center gap-3 px-3 py-2.5 rounded-md
text-sm transition-all duration-150
${active
? "bg-elevated text-primary border-l-2 border-accent pl-[10px]"
: "text-secondary hover:text-primary hover:bg-elevated/50"
}`}>
<Icon size={16} />
<span className="font-medium">{label}</span>
</Link>
);
})}
</nav>

{/* Footer */}
<div className="px-4 py-4 border-t border-border space-y-3">
{/* Mode badge */}
<div className="flex items-center gap-2">
<span className={`text-xs font-label px-2 py-0.5 rounded
${health?.trading.mode === "LIVE"
? "bg-profit-dim text-profit"
: "bg-warning-dim text-warning"}`}>
{health?.trading.mode ?? "—"}
</span>
{health?.trading.mode === "LIVE" && (
<span className="w-1.5 h-1.5 rounded-full bg-profit animate-pulse" />
)}
</div>
{/* System health */}
<div className="flex items-center gap-2 text-xs text-tertiary">
<StatusDot status={health?.status ?? "offline"} />
<span>{health?.status === "healthy" ? "All systems online" : "Degraded"}</span>
</div>
</div>
</aside>
);
}

## 4.2 signals/SignalCard.tsx
The signal card is the central UI component of Lumitrade. It must communicate a complex trading decision clearly and immediately. The card has two states: collapsed (summary view) and expanded (full AI reasoning + indicators).

// components/signals/SignalCard.tsx
"use client";
import { useState } from "react";
import { ChevronDown, ChevronUp, Zap, AlertTriangle } from "lucide-react";
import type { Signal } from "@/types/trading";
import ConfidenceBar from "./ConfidenceBar";
import TimeframeScores from "./TimeframeScores";
import SignalDetailPanel from "./SignalDetailPanel";
import Badge from "@/components/ui/Badge";
import { formatPrice, formatTime, formatPips } from "@/lib/formatters";

interface Props { signal: Signal; }

export default function SignalCard({ signal }: Props) {
const [expanded, setExpanded] = useState(false);

const actionColor = {
BUY:  "text-profit border-profit",
SELL: "text-loss border-loss",
HOLD: "text-secondary border-border",
}[signal.action];

const leftBorder = signal.executed
? "border-l-2 border-l-profit"
: signal.rejection_reason
? "border-l-2 border-l-loss"
: "border-l-2 border-l-transparent";

return (
<div className={`bg-surface rounded-lg border border-border ${leftBorder}
transition-all duration-200 hover:border-border-accent`}>

{/* Collapsed header — always visible */}
<div
className="flex items-start gap-4 p-4 cursor-pointer"
onClick={() => signal.action !== "HOLD" && setExpanded(!expanded)}
>
{/* Pair + Action */}
<div className="flex-1 min-w-0">
<div className="flex items-center gap-2 mb-1.5">
<span className="font-mono text-sm font-medium text-primary">
{signal.pair.replace("_", "/")}
</span>
<Badge action={signal.action} />
{signal.generation_method === "RULE_BASED" && (
<span className="text-xs px-1.5 py-0.5 rounded bg-warning-dim text-warning">
RULE-BASED
</span>
)}
{signal.executed && (
<span className="text-xs px-1.5 py-0.5 rounded bg-profit-dim text-profit">
EXECUTED
</span>
)}
{signal.rejection_reason && (
<span className="text-xs px-1.5 py-0.5 rounded bg-loss-dim text-loss">
{signal.rejection_reason}
</span>
)}
</div>

{/* Confidence bar */}
{signal.action !== "HOLD" && (
<ConfidenceBar value={signal.confidence_adjusted} />
)}

{/* Summary */}
<p className="text-secondary text-sm mt-2 leading-relaxed line-clamp-2">
{signal.summary}
</p>
</div>

{/* Timestamp + expand toggle */}
<div className="flex flex-col items-end gap-2 flex-shrink-0">
<span className="text-tertiary text-xs font-mono">
{formatTime(signal.created_at)}
</span>
{signal.action !== "HOLD" && (
expanded ? <ChevronUp size={14} className="text-tertiary" />
: <ChevronDown size={14} className="text-tertiary" />
)}
</div>
</div>

{/* Expanded detail panel */}
{expanded && <SignalDetailPanel signal={signal} />}
</div>
);
}

## 4.3 signals/SignalDetailPanel.tsx
The detail panel renders inside the expanded signal card. It presents the full technical breakdown in a structured, readable format.

// components/signals/SignalDetailPanel.tsx
"use client";
import type { Signal } from "@/types/trading";
import TimeframeScores from "./TimeframeScores";
import { formatPrice } from "@/lib/formatters";

interface Props { signal: Signal; }

export default function SignalDetailPanel({ signal }: Props) {
const ind = signal.indicators_snapshot;
const rr = calcRR(signal);

return (
<div className="border-t border-border px-4 pb-4 pt-3 space-y-4">

{/* Entry / SL / TP row */}
<div className="grid grid-cols-3 gap-3">
<PriceBox label="Entry" value={signal.entry_price} color="text-primary" />
<PriceBox label="Stop Loss" value={signal.stop_loss} color="text-loss" />
<PriceBox label="Take Profit" value={signal.take_profit} color="text-profit" />
</div>

{/* R:R ratio */}
<div className="flex items-center gap-2">
<span className="text-label text-tertiary">Risk / Reward</span>
<span className="font-mono text-sm text-primary">{rr.toFixed(2)} : 1</span>
<span className="text-xs text-secondary">
({signal.spread_pips} pip spread at signal time)
</span>
</div>

{/* Timeframe confluence */}
<div>
<p className="text-label text-tertiary mb-2">Timeframe Confluence</p>
<TimeframeScores scores={signal.timeframe_scores} />
</div>

{/* Indicators table */}
{ind && (
<div>
<p className="text-label text-tertiary mb-2">Indicators at Signal</p>
<div className="grid grid-cols-2 gap-1.5">
<IndRow label="RSI (14)" value={ind.rsi_14}
signal={+ind.rsi_14 < 30 ? "+" : +ind.rsi_14 > 70 ? "-" : "~"} />
<IndRow label="MACD Histogram" value={ind.macd_histogram}
signal={+ind.macd_histogram > 0 ? "+" : "-"} />
<IndRow label="EMA 20" value={ind.ema_20} signal="~" />
<IndRow label="EMA 50" value={ind.ema_50} signal="~" />
<IndRow label="EMA 200" value={ind.ema_200} signal="~" />
<IndRow label="ATR (14)" value={ind.atr_14} signal="~" />
</div>
</div>
)}

{/* Confidence adjustment breakdown */}
{Object.keys(signal.confidence_adjustment_log).length > 0 && (
<div>
<p className="text-label text-tertiary mb-2">Confidence Adjustments</p>
<div className="space-y-1">
{Object.entries(signal.confidence_adjustment_log).map(([k, v]) => (
<div key={k} className="flex justify-between text-xs">
<span className="text-secondary capitalize">{k.replace(/_/g, " ")}</span>
<span className={`font-mono ${v >= 0 ? "text-profit" : "text-loss"}`}>
{v >= 0 ? "+" : ""}{(v as number).toFixed(2)}
</span>
</div>
))}
</div>
</div>
)}

{/* News context */}
{signal.news_context?.length > 0 && (
<div>
<p className="text-label text-tertiary mb-2">Active News Events</p>
{signal.news_context.map((e, i) => (
<div key={i} className="flex items-center gap-2 text-xs mb-1">
<span className={`px-1.5 py-0.5 rounded text-xs
${e.impact === "HIGH" ? "bg-loss-dim text-loss" : "bg-warning-dim text-warning"}`}>
{e.impact}
</span>
<span className="text-secondary">{e.title}</span>
<span className="text-tertiary font-mono">
{e.minutes_until > 0 ? `in ${e.minutes_until}m` : "now"}
</span>
</div>
))}
</div>
)}

{/* Full AI reasoning */}
<div>
<p className="text-label text-tertiary mb-2">AI Reasoning</p>
<p className="text-secondary text-sm leading-relaxed bg-input
rounded-md p-3 font-mono text-xs whitespace-pre-wrap">
{signal.reasoning}
</p>
</div>
</div>
);
}

// Helper sub-components
function PriceBox({ label, value, color }: { label:string; value:string; color:string }) {
return (
<div className="bg-input rounded-md p-2.5">
<p className="text-tertiary text-xs font-label mb-1">{label}</p>
<p className={`font-mono text-sm font-medium ${color}`}>{value}</p>
</div>
);
}

function IndRow({ label, value, signal }: { label:string; value:string; signal:string }) {
const color = signal === "+" ? "text-profit" : signal === "-" ? "text-loss" : "text-secondary";
return (
<div className="flex justify-between items-center bg-input rounded px-2.5 py-1.5">
<span className="text-xs text-tertiary">{label}</span>
<span className={`font-mono text-xs ${color}`}>{value}</span>
</div>
);
}

function calcRR(s: Signal): number {
const entry = parseFloat(s.entry_price);
const sl    = parseFloat(s.stop_loss);
const tp    = parseFloat(s.take_profit);
const risk  = Math.abs(entry - sl);
const reward= Math.abs(tp - entry);
return risk > 0 ? reward / risk : 0;
}

# 5. Real-Time Data Hooks
## 5.1 hooks/useRealtime.ts — Base Realtime Hook
// Generic Supabase Realtime subscription hook
"use client";
import { useEffect, useRef, useCallback } from "react";
import { createBrowserClient } from "@supabase/ssr";
import type { RealtimeChannel } from "@supabase/supabase-js";

interface UseRealtimeOptions {
table: string;
event?: "INSERT" | "UPDATE" | "DELETE" | "*";
filter?: string;
onData: (payload: any) => void;
}

export function useRealtime({
table, event = "*", filter, onData
}: UseRealtimeOptions) {
const supabase = createBrowserClient(
process.env.NEXT_PUBLIC_SUPABASE_URL!,
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);
const channelRef = useRef<RealtimeChannel | null>(null);
const onDataRef  = useRef(onData);
onDataRef.current = onData;

useEffect(() => {
const channel = supabase
.channel(`realtime:${table}`)
.on("postgres_changes",
{ event, schema: "public", table, filter },
(payload) => onDataRef.current(payload)
)
.subscribe();
channelRef.current = channel;
return () => { supabase.removeChannel(channel); };
}, [table, event, filter]);
}

## 5.2 hooks/useSignals.ts
"use client";
import { useState, useEffect, useCallback } from "react";
import type { Signal } from "@/types/trading";
import { useRealtime } from "./useRealtime";

const MAX_SIGNALS = 50;

export function useSignals() {
const [signals, setSignals] = useState<Signal[]>([]);
const [loading, setLoading]  = useState(true);
const [error, setError]      = useState<string | null>(null);

// Initial fetch
useEffect(() => {
fetch("/api/signals?limit=50")
.then(r => r.json())
.then(data => { setSignals(data.signals); setLoading(false); })
.catch(e => { setError(e.message); setLoading(false); });
}, []);

// Real-time subscription — prepend new signals
useRealtime({
table: "signals",
event: "INSERT",
onData: useCallback((payload) => {
setSignals(prev => [payload.new as Signal, ...prev].slice(0, MAX_SIGNALS));
}, []),
});

// Real-time subscription — update signal when executed flag changes
useRealtime({
table: "signals",
event: "UPDATE",
onData: useCallback((payload) => {
setSignals(prev =>
prev.map(s => s.id === payload.new.id ? payload.new as Signal : s)
);
}, []),
});

return { signals, loading, error };
}

## 5.3 hooks/useOpenPositions.ts
"use client";
import { useState, useEffect, useCallback } from "react";
import type { OpenPosition } from "@/types/trading";
import { useRealtime } from "./useRealtime";

export function useOpenPositions() {
const [positions, setPositions] = useState<OpenPosition[]>([]);
const [loading, setLoading]     = useState(true);

useEffect(() => {
fetch("/api/positions/open")
.then(r => r.json())
.then(data => { setPositions(data.positions); setLoading(false); });
}, []);

// New trade opened
useRealtime({
table: "trades",
event: "INSERT",
filter: "status=eq.OPEN",
onData: useCallback((payload) => {
setPositions(prev => [...prev, payload.new as OpenPosition]);
}, []),
});

// Trade closed — remove from open positions
useRealtime({
table: "trades",
event: "UPDATE",
onData: useCallback((payload) => {
const updated = payload.new;
if (updated.status === "CLOSED" || updated.status === "CANCELLED") {
setPositions(prev => prev.filter(p => p.id !== updated.id));
} else {
setPositions(prev =>
prev.map(p => p.id === updated.id ? updated as OpenPosition : p)
);
}
}, []),
});

return { positions, loading };
}

## 5.4 hooks/useSystemStatus.ts
"use client";
import { useState, useEffect } from "react";
import type { SystemHealth } from "@/types/system";

const POLL_INTERVAL = 30_000; // 30 seconds

export function useSystemStatus() {
const [health, setHealth]   = useState<SystemHealth | null>(null);
const [loading, setLoading] = useState(true);

useEffect(() => {
const fetchHealth = async () => {
try {
const res = await fetch("/api/system/health");
if (res.ok) setHealth(await res.json());
} catch { /* Network error — keep last known state */ }
finally { setLoading(false); }
};

fetchHealth();
const interval = setInterval(fetchHealth, POLL_INTERVAL);
return () => clearInterval(interval);
}, []);

return { health, loading };
}

# 6. Dashboard Page Implementation
## 6.1 dashboard/page.tsx — Main Dashboard
"use client";
import AccountPanel        from "@/components/dashboard/AccountPanel";
import TodayPanel          from "@/components/dashboard/TodayPanel";
import SystemStatusPanel   from "@/components/dashboard/SystemStatusPanel";
import OpenPositionsTable  from "@/components/dashboard/OpenPositionsTable";
import { SignalFeed }       from "@/components/signals/SignalFeed";
import KillSwitchButton     from "@/components/dashboard/KillSwitchButton";

export default function DashboardPage() {
return (
<div className="space-y-4">

{/* Top row: Account + Today + System Status */}
<div className="grid grid-cols-3 gap-4">
<AccountPanel />
<TodayPanel />
<SystemStatusPanel />
</div>

{/* Mid row: Open Positions + Recent Signals */}
<div className="grid grid-cols-5 gap-4">
<div className="col-span-3">
<OpenPositionsTable />
</div>
<div className="col-span-2">
<SignalFeed limit={8} compact />
</div>
</div>

{/* Kill switch — visible but not prominent */}
<div className="flex justify-end">
<KillSwitchButton />
</div>

</div>
);
}

## 6.2 dashboard/SystemStatusPanel.tsx
"use client";
import { useSystemStatus } from "@/hooks/useSystemStatus";
import StatusDot from "@/components/ui/StatusDot";

const COMPONENTS = [
{ key: "oanda_api",     label: "OANDA API"      },
{ key: "ai_brain",      label: "AI Brain"       },
{ key: "database",      label: "Database"       },
{ key: "price_feed",    label: "Price Feed"     },
{ key: "risk_engine",   label: "Risk Engine"    },
{ key: "circuit_breaker", label: "Circuit Brk"  },
] as const;

export default function SystemStatusPanel() {
const { health, loading } = useSystemStatus();

return (
<div className="bg-surface border border-border rounded-lg p-5">
<div className="flex items-center justify-between mb-4">
<h3 className="text-card-title text-primary">System Status</h3>
<StatusDot status={health?.status ?? "offline"} size="md" showLabel />
</div>

<div className="space-y-2.5">
{COMPONENTS.map(({ key, label }) => {
const comp = health?.components[key as keyof typeof health.components];
const status = loading ? "loading" : (comp?.status ?? "offline");
const extra = key === "risk_engine" && health
? ` · ${health.components.risk_engine.state}`
: key === "circuit_breaker" && health
? ` · ${health.components.circuit_breaker.status}`
: "";

return (
<div key={key} className="flex items-center justify-between">
<span className="text-secondary text-sm">{label}</span>
<div className="flex items-center gap-2">
{extra && (
<span className="text-tertiary text-xs font-mono">{extra}</span>
)}
<StatusDot status={status as any} />
</div>
</div>
);
})}
</div>
</div>
);
}

## 6.3 dashboard/KillSwitchButton.tsx
The kill switch is the most consequential UI control. Its design must prevent accidental activation while remaining accessible in an emergency. It requires a two-step confirmation with a typed acknowledgment.

"use client";
import { useState } from "react";
import { AlertTriangle, X } from "lucide-react";

export default function KillSwitchButton() {
const [step, setStep]     = useState<"idle"|"confirm"|"typing"|"loading">("idle");
const [typed, setTyped]   = useState("");
const CONFIRM_TEXT        = "HALT TRADING";

const activate = async () => {
if (typed !== CONFIRM_TEXT) return;
setStep("loading");
try {
const res = await fetch("/api/control/kill-switch", { method: "POST" });
if (res.ok) {
alert("Emergency halt activated. All trading stopped.");
}
} finally {
setStep("idle");
setTyped("");
}
};

if (step === "idle") {
return (
<button
onClick={() => setStep("confirm")}
className="flex items-center gap-2 px-3 py-1.5 rounded border
border-loss/30 text-loss/70 text-xs hover:border-loss
hover:text-loss hover:bg-loss-dim transition-all duration-150">
<AlertTriangle size={12} />
Emergency Halt
</button>
);
}

return (
<div className="bg-surface border border-loss rounded-lg p-4 w-80">
<div className="flex items-start justify-between mb-3">
<div className="flex items-center gap-2 text-loss">
<AlertTriangle size={16} />
<span className="font-medium text-sm">Confirm Emergency Halt</span>
</div>
<button onClick={() => { setStep("idle"); setTyped(""); }}>
<X size={14} className="text-tertiary hover:text-primary" />
</button>
</div>
<p className="text-secondary text-xs mb-3">
This will immediately stop all signal scanning and close all open
positions at market price. Type <strong className="text-primary">
HALT TRADING</strong> to confirm.
</p>
<input
autoFocus
value={typed}
onChange={e => setTyped(e.target.value)}
placeholder="Type HALT TRADING"
className="w-full bg-input border border-border rounded px-3 py-2
text-sm font-mono text-primary placeholder-tertiary
focus:outline-none focus:border-loss mb-3"
/>
<button
disabled={typed !== CONFIRM_TEXT || step === "loading"}
onClick={activate}
className="w-full py-2 rounded bg-loss/10 border border-loss text-loss
text-sm font-medium disabled:opacity-30 disabled:cursor-not-allowed
hover:bg-loss/20 transition-colors duration-150">
{step === "loading" ? "Activating..." : "Activate Emergency Halt"}
</button>
</div>
);
}

# 7. Analytics Components
## 7.1 analytics/EquityCurve.tsx
"use client";
import {
ResponsiveContainer, AreaChart, Area,
XAxis, YAxis, Tooltip, ReferenceLine
} from "recharts";
import type { PerformanceSummary } from "@/types/system";

interface Props {
data: PerformanceSummary["equity_curve"];
startingBalance: number;
}

export default function EquityCurve({ data, startingBalance }: Props) {
const maxEquity = Math.max(...data.map(d => d.equity));
const minEquity = Math.min(...data.map(d => d.equity));
const isPositive = data[data.length - 1]?.equity >= startingBalance;

return (
<div className="bg-surface border border-border rounded-lg p-5">
<h3 className="text-card-title text-primary mb-4">Equity Curve</h3>

<ResponsiveContainer width="100%" height={200}>
<AreaChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
<defs>
<linearGradient id="equity-fill" x1="0" y1="0" x2="0" y2="1">
<stop offset="0%"
stopColor={isPositive ? "#00C896" : "#FF4D6A"}
stopOpacity={0.3} />
<stop offset="100%"
stopColor={isPositive ? "#00C896" : "#FF4D6A"}
stopOpacity={0.02} />
</linearGradient>
</defs>
<XAxis dataKey="date"
tick={{ fill: "#4A5E80", fontSize: 11, fontFamily: "JetBrains Mono" }}
axisLine={{ stroke: "#1E3050" }} tickLine={false}
tickFormatter={(v) => v.slice(5)} />
<YAxis
domain={[minEquity * 0.99, maxEquity * 1.01]}
tick={{ fill: "#4A5E80", fontSize: 11, fontFamily: "JetBrains Mono" }}
axisLine={{ stroke: "#1E3050" }} tickLine={false}
tickFormatter={(v) => `$${v.toFixed(0)}`} />
<Tooltip
contentStyle={{
background: "#111D2E",
border: "1px solid #1E3050",
borderRadius: "6px",
fontFamily: "JetBrains Mono",
fontSize: "12px",
}}
labelStyle={{ color: "#8A9BC0" }}
itemStyle={{ color: isPositive ? "#00C896" : "#FF4D6A" }}
formatter={(v: number) => [`$${v.toFixed(2)}`, "Equity"]}
/>
<ReferenceLine y={startingBalance}
stroke="#1E3050" strokeDasharray="4 4" />
<Area type="monotone" dataKey="equity"
stroke={isPositive ? "#00C896" : "#FF4D6A"}
strokeWidth={1.5}
fill="url(#equity-fill)" />
</AreaChart>
</ResponsiveContainer>
</div>
);
}

## 7.2 analytics/MetricsGrid.tsx
"use client";
import type { PerformanceSummary } from "@/types/system";

interface Props { metrics: PerformanceSummary; }

const METRICS = [
{ key: "win_rate",              label: "Win Rate",       fmt: (v:number) => `${(v*100).toFixed(1)}%`,  positive: (v:number) => v >= 0.5 },
{ key: "profit_factor",         label: "Profit Factor",  fmt: (v:number) => v.toFixed(2),              positive: (v:number) => v >= 1.3 },
{ key: "sharpe_ratio",          label: "Sharpe Ratio",   fmt: (v:number) => v.toFixed(2),              positive: (v:number) => v >= 1.0 },
{ key: "max_drawdown_pct",      label: "Max Drawdown",   fmt: (v:number) => `${(v*100).toFixed(1)}%`,  positive: (v:number) => v <= 0.10 },
{ key: "avg_win_pips",          label: "Avg Win",        fmt: (v:number) => `${v.toFixed(1)} pips`,    positive: () => true },
{ key: "avg_loss_pips",         label: "Avg Loss",       fmt: (v:number) => `${v.toFixed(1)} pips`,    positive: () => false },
{ key: "total_trades",          label: "Total Trades",   fmt: (v:number) => String(v),                 positive: () => true },
{ key: "expectancy_per_trade_usd", label: "Expectancy",  fmt: (v:number) => `$${v.toFixed(2)}`,        positive: (v:number) => v > 0 },
];

export default function MetricsGrid({ metrics }: Props) {
return (
<div className="grid grid-cols-4 gap-3">
{METRICS.map(({ key, label, fmt, positive }) => {
const val = metrics[key as keyof PerformanceSummary] as number;
const good = positive(val);
return (
<div key={key} className="bg-surface border border-border rounded-lg p-4">
<p className="text-label text-tertiary mb-1">{label}</p>
<p className={`text-metric ${good ? "text-profit" : "text-loss"}`}>
{fmt(val)}
</p>
</div>
);
})}
</div>
);
}

# 8. Tailwind Configuration & Global CSS
## 8.1 tailwind.config.ts
import type { Config } from "tailwindcss";

const config: Config = {
content: ["./src/**/*.{ts,tsx}"],
theme: {
extend: {
colors: {
brand:   "var(--color-bg-primary)",
surface: "var(--color-bg-surface)",
elevated:"var(--color-bg-elevated)",
input:   "var(--color-bg-input)",
border:  { DEFAULT: "var(--color-border)", accent: "var(--color-border-accent)" },
primary: "var(--color-text-primary)",
secondary:"var(--color-text-secondary)",
tertiary:"var(--color-text-tertiary)",
accent:  "var(--color-accent)",
profit:  "var(--color-profit)",
loss:    "var(--color-loss)",
warning: "var(--color-warning)",
gold:    "var(--color-gold)",
},
fontFamily: {
sans:    ["DM Sans", "sans-serif"],
mono:    ["JetBrains Mono", "monospace"],
display: ["Space Grotesk", "sans-serif"],
},
backgroundOpacity: { "dim": "0.12" },
},
},
plugins: [],
};
export default config;

## 8.2 app/globals.css
@import url("https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@600&display=swap");

@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
/* Background */
--color-bg-primary:   #0D1B2A;
--color-bg-surface:   #111D2E;
--color-bg-elevated:  #1A2840;
--color-bg-input:     #0A1628;

/* Borders */
--color-border:        #1E3050;
--color-border-accent: #2A4070;

/* Text */
--color-text-primary:   #E8F0FE;
--color-text-secondary: #8A9BC0;
--color-text-tertiary:  #4A5E80;

/* Semantic */
--color-accent:      #3D8EFF;
--color-accent-glow: rgba(61,142,255,0.15);
--color-profit:      #00C896;
--color-profit-dim:  rgba(0,200,150,0.12);
--color-loss:        #FF4D6A;
--color-loss-dim:    rgba(255,77,106,0.12);
--color-warning:     #FFB347;
--color-warning-dim: rgba(255,179,71,0.12);
--color-gold:        #E67E22;
}

body {
background-color: var(--color-bg-primary);
color: var(--color-text-primary);
font-family: "DM Sans", sans-serif;
-webkit-font-smoothing: antialiased;
}

/* ── Utility classes ───────────────────────────────────────── */
.text-display   { font-family: "Space Grotesk"; font-size: 28px; font-weight: 600; }
.text-heading   { font-size: 18px; font-weight: 600; }
.text-card-title{ font-size: 14px; font-weight: 500; }
.text-body      { font-size: 14px; font-weight: 400; }
.text-label     { font-size: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
.text-price     { font-family: "JetBrains Mono"; font-size: 16px; font-weight: 500; }
.text-metric    { font-family: "JetBrains Mono"; font-size: 24px; font-weight: 600; }
.text-micro     { font-family: "JetBrains Mono"; font-size: 11px; font-weight: 400; }

/* ── Profit/Loss color utilities ───────────────────────────── */
.text-profit    { color: var(--color-profit); }
.text-loss      { color: var(--color-loss); }
.text-warning   { color: var(--color-warning); }
.text-gold      { color: var(--color-gold); }
.text-accent    { color: var(--color-accent); }
.bg-profit-dim  { background-color: var(--color-profit-dim); }
.bg-loss-dim    { background-color: var(--color-loss-dim); }
.bg-warning-dim { background-color: var(--color-warning-dim); }
.bg-input       { background-color: var(--color-bg-input); }
.bg-surface     { background-color: var(--color-bg-surface); }
.bg-elevated    { background-color: var(--color-bg-elevated); }
.border-border  { border-color: var(--color-border); }
.border-loss    { border-color: var(--color-loss); }
.border-profit  { border-color: var(--color-profit); }

# 9. Next.js API Routes
## 9.1 api/account/route.ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function GET() {
const cookieStore = cookies();
const supabase = createServerClient(
process.env.NEXT_PUBLIC_SUPABASE_URL!,
process.env.SUPABASE_SERVICE_KEY!,
{ cookies: { get: (name) => cookieStore.get(name)?.value } }
);

// Get latest system_state for today's P&L and trade counts
const { data: state } = await supabase
.from("system_state")
.select("*")
.eq("id", "singleton")
.single();

// Get today's trade stats
const today = new Date().toISOString().split("T")[0];
const { data: todayTrades } = await supabase
.from("trades")
.select("outcome, pnl_usd")
.gte("opened_at", today)
.eq("status", "CLOSED");

const wins     = todayTrades?.filter(t => t.outcome === "WIN").length ?? 0;
const total    = todayTrades?.length ?? 0;
const win_rate = total > 0 ? (wins / total) : 0;

return NextResponse.json({
balance:          state?.daily_opening_balance ?? 0,
daily_pnl_usd:    state?.daily_pnl_usd ?? 0,
daily_pnl_pct:    state?.daily_opening_balance
? state.daily_pnl_usd / state.daily_opening_balance
: 0,
daily_trade_count:total,
daily_win_count:  wins,
daily_win_rate:   win_rate,
open_trade_count: state?.open_trades?.length ?? 0,
mode:             process.env.TRADING_MODE ?? "PAPER",
});
}

## 9.2 api/control/kill-switch/route.ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function POST() {
const cookieStore = cookies();
const supabase = createServerClient(
process.env.NEXT_PUBLIC_SUPABASE_URL!,
process.env.SUPABASE_SERVICE_KEY!,
{ cookies: { get: (name) => cookieStore.get(name)?.value } }
);

// Write EMERGENCY_HALT to system_state
// The Python engine reads this on next state refresh cycle (max 60s)
const { error } = await supabase
.from("system_state")
.update({
risk_state: "EMERGENCY_HALT",
updated_at: new Date().toISOString(),
})
.eq("id", "singleton");

if (error) {
return NextResponse.json(
{ error: "Failed to activate kill switch" },
{ status: 500 }
);
}

// Log the event
await supabase.from("system_events").insert({
event_type:  "KILL_SWITCH_ACTIVATED",
detail:      "Emergency halt activated via dashboard",
triggered_by:"DASHBOARD_USER",
created_at:  new Date().toISOString(),
});

return NextResponse.json({ success: true, state: "EMERGENCY_HALT" });
}

# 10. Formatters & Shared Utilities
## 10.1 lib/formatters.ts
// All display formatting for prices, P&L, dates, and pair names

/**
* Format a forex price with appropriate decimal places.
* EUR/USD: 5 decimal places. USD/JPY: 3 decimal places.
*/
export function formatPrice(price: string | number, pair?: string): string {
const n = typeof price === "string" ? parseFloat(price) : price;
if (isNaN(n)) return "—";
const decimals = pair?.includes("JPY") ? 3 : 5;
return n.toFixed(decimals);
}

/**
* Format P&L with sign and color class.
* Returns { formatted: "+$4.23", colorClass: "text-profit" }
*/
export function formatPnl(
value: string | number | null
): { formatted: string; colorClass: string } {
if (value === null || value === undefined) {
return { formatted: "—", colorClass: "text-tertiary" };
}
const n = typeof value === "string" ? parseFloat(value) : value;
if (isNaN(n)) return { formatted: "—", colorClass: "text-tertiary" };
const sign = n >= 0 ? "+" : "";
return {
formatted:  `${sign}$${Math.abs(n).toFixed(2)}`,
colorClass: n > 0 ? "text-profit" : n < 0 ? "text-loss" : "text-secondary",
};
}

/**
* Format pips with sign.
*/
export function formatPips(pips: string | number | null): string {
if (pips === null || pips === undefined) return "—";
const n = typeof pips === "string" ? parseFloat(pips) : pips;
if (isNaN(n)) return "—";
const sign = n >= 0 ? "+" : "";
return `${sign}${n.toFixed(1)}p`;
}

/**
* Format pair name for display: EUR_USD → EUR/USD
*/
export function formatPair(pair: string): string {
return pair.replace("_", "/");
}

/**
* Format a timestamp for the signal feed.
* Same day: "14:32" — previous day: "Mar 19 14:32"
*/
export function formatTime(isoString: string): string {
const date = new Date(isoString);
const now  = new Date();
const sameDay = date.toDateString() === now.toDateString();
if (sameDay) {
return date.toLocaleTimeString("en-US", {
hour: "2-digit", minute: "2-digit", hour12: false
});
}
return date.toLocaleDateString("en-US", {
month: "short", day: "numeric", hour: "2-digit",
minute: "2-digit", hour12: false
});
}

/**
* Format duration in minutes to human-readable.
* 75 → "1h 15m"  |  45 → "45m"  |  1380 → "23h"
*/
export function formatDuration(minutes: number | null): string {
if (!minutes) return "—";
if (minutes < 60) return `${minutes}m`;
const h = Math.floor(minutes / 60);
const m = minutes % 60;
return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

/**
* Format confidence as percentage string.
* 0.82 → "82%"
*/
export function formatConfidence(confidence: number): string {
return `${Math.round(confidence * 100)}%`;
}

# 11. Configuration Files
## 11.1 package.json
{
"name": "lumitrade-dashboard",
"version": "1.0.0",
"private": true,
"scripts": {
"dev":   "next dev",
"build": "next build",
"start": "next start",
"lint":  "next lint",
"type-check": "tsc --noEmit"
},
"dependencies": {
"next":           "14.2.3",
"react":          "18.3.1",
"react-dom":      "18.3.1",
"@supabase/ssr":  "0.3.0",
"@supabase/supabase-js": "2.43.1",
"recharts":       "2.12.4",
"lucide-react":   "0.383.0",
"clsx":           "2.1.1",
"tailwind-merge": "2.3.0"
},
"devDependencies": {
"typescript":         "5.4.5",
"@types/react":       "18.3.1",
"@types/node":        "20.12.7",
"tailwindcss":        "3.4.3",
"autoprefixer":       "10.4.19",
"postcss":            "8.4.38",
"@tailwindcss/forms": "0.5.7",
"eslint":             "8.57.0",
"eslint-config-next": "14.2.3"
}
}

## 11.2 next.config.ts
import type { NextConfig } from "next";

const config: NextConfig = {
// Security headers
async headers() {
return [{
source: "/(.*)",
headers: [
{ key: "X-Frame-Options",           value: "DENY"            },
{ key: "X-Content-Type-Options",    value: "nosniff"         },
{ key: "Referrer-Policy",           value: "strict-origin"   },
{ key: "Permissions-Policy",        value: "camera=(), microphone=()" },
],
}];
},
// Environment variables exposed to browser (non-secret only)
env: {
NEXT_PUBLIC_SUPABASE_URL:      process.env.NEXT_PUBLIC_SUPABASE_URL!,
NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
},
};

export default config;

## 11.3 Environment Variables (.env.local)
# Supabase — public (safe to expose to browser)
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key

# Supabase — server only (never expose to browser)
SUPABASE_SERVICE_KEY=your-service-role-key

# Trading mode — read by API routes for display
TRADING_MODE=PAPER
Security Rule  SUPABASE_SERVICE_KEY must NEVER be prefixed with NEXT_PUBLIC_. If it is, it will be exposed in the browser bundle and any user can access all data. The service key is server-only.

# 12. Component Build Checklist
## 12.1 Build Order (dependency-safe sequence)
Build components in this order to avoid import errors. Each row must be complete before starting the next.




END OF DOCUMENT
Lumitrade Frontend Developer Specification v1.0  |  Confidential
Next Document: DevOps Specification (Role 5)





LUMITRADE
Frontend Developer Specification

ROLE 4 — SENIOR FRONTEND DEVELOPER
All original dashboard + future page stubs and route placeholders
Version 2.0  |  Includes future feature foundations
Date: March 21, 2026




# 1–12. All Original FDS Sections
All original Frontend Developer Specification content is unchanged: design system, app structure, TypeScript types, component specifications, real-time hooks, dashboard page, analytics, Tailwind config, API routes, formatters, package.json, and build order checklist.
Reference  Original FDS v1.0 is the authoritative source for all Phase 0 frontend implementation. This document adds Section 13 only.

# 13. Future Feature Frontend Foundations
## 13.1 Extended Navigation — Sidebar
Update the Sidebar.tsx NAV_ITEMS array to include future pages. Stub pages show a "coming soon" badge and are accessible but display placeholder content.

const NAV_ITEMS = [
// Phase 0 — fully implemented
{ href: "/dashboard",     label: "Dashboard",    icon: LayoutDashboard, phase: 0 },
{ href: "/signals",       label: "Signals",      icon: Zap,             phase: 0 },
{ href: "/trades",        label: "Trades",       icon: History,         phase: 0 },
{ href: "/analytics",     label: "Analytics",    icon: BarChart2,        phase: 0 },
{ href: "/settings",      label: "Settings",     icon: Settings,        phase: 0 },
// Phase 2 — stub pages (visible, show coming soon)
{ href: "/journal",       label: "Journal",      icon: BookOpen,        phase: 2 },
{ href: "/coach",         label: "AI Coach",     icon: MessageCircle,   phase: 2 },
{ href: "/intelligence",  label: "Intel Report", icon: TrendingUp,      phase: 2 },
// Phase 3 — stub pages (visible, show coming soon)
{ href: "/marketplace",   label: "Marketplace",  icon: Store,           phase: 3 },
{ href: "/copy",          label: "Copy Trading", icon: Users,           phase: 3 },
{ href: "/backtest",      label: "Backtest",     icon: FlaskConical,    phase: 3 },
{ href: "/api-keys",      label: "API Access",   icon: Key,             phase: 3 },
];

// In the nav render, stub pages get a phase badge:
// { phase > 0 && <span className="text-xs text-tertiary">Phase {phase}</span> }

## 13.2 Stub Page Component
One reusable component for all future pages. Renders a consistent "coming soon" panel:

// components/ui/ComingSoon.tsx
"use client";
interface Props {
feature: string;
phase: number;
description: string;
unlockCondition: string;
}

export default function ComingSoon({ feature, phase, description, unlockCondition }: Props) {
return (
<div className="flex flex-col items-center justify-center min-h-96 gap-4">
<div className="bg-surface border border-border rounded-lg p-8 max-w-md text-center">
<span className="text-xs font-label text-warning bg-warning-dim px-2 py-1 rounded mb-4 inline-block">
Phase {phase} Feature
</span>
<h2 className="text-heading-md text-primary mt-3 mb-2">{feature}</h2>
<p className="text-secondary text-body-md mb-4">{description}</p>
<p className="text-tertiary text-body-sm">
Unlocks when: {unlockCondition}
</p>
</div>
</div>
);
}

## 13.3 Stub Page Implementations
Create these files now. Each is a minimal page that renders the ComingSoon component:

// app/journal/page.tsx
import ComingSoon from "@/components/ui/ComingSoon";
export default function JournalPage() {
return <ComingSoon
feature="Trade Journal AI"
phase={2}
description="Every Sunday, AI writes a plain-English summary of your trading week — best trade, worst trade, key insight, one recommendation."
unlockCondition="50+ completed live trades"
/>;
}

// app/coach/page.tsx
import ComingSoon from "@/components/ui/ComingSoon";
export default function CoachPage() {
return <ComingSoon
feature="AI Trading Coach"
phase={2}
description="Ask questions about any trade. The AI explains what happened, why, and what to adjust. Powered by your actual trade history."
unlockCondition="100+ completed live trades"
/>;
}

// app/intelligence/page.tsx — Phase 2
// app/marketplace/page.tsx  — Phase 3
// app/copy/page.tsx         — Phase 3
// app/backtest/page.tsx     — Phase 3
// app/api-keys/page.tsx     — Phase 3
// (all follow same ComingSoon pattern)

## 13.4 Extended TypeScript Types
Add to types/trading.ts — these types are needed even in Phase 0 so dashboard components can reference future data without TypeScript errors:

// types/future.ts — new file

export type MarketRegime = "TRENDING" | "RANGING" | "HIGH_VOLATILITY" | "LOW_LIQUIDITY" | "UNKNOWN";
export type CurrencySentiment = "BULLISH" | "BEARISH" | "NEUTRAL";
export type AssetClass = "FOREX" | "CRYPTO" | "STOCKS" | "OPTIONS";

export interface TradeJournal {
id: string;
week_start: string;
content_text: string;
win_rate_vs_prior: number | null;
recommendation: string;
generated_at: string;
}

export interface RuinAnalysis {
prob_loss_25pct: number;
prob_loss_50pct: number;
prob_loss_100pct: number;
status: "SAFE" | "WARNING" | "DANGER" | "INSUFFICIENT_DATA";
sample_size: number;
is_sufficient: boolean;
}

export interface Strategy {
id: string;
name: string;
description: string;
creator_name: string;
win_rate: number;
profit_factor: number;
subscriber_count: number;
price_monthly: number;
live_since: string;
}

export interface RegimeDisplay {
regime: MarketRegime;
label: string;
color: "profit" | "loss" | "warning" | "secondary";
}

## 13.5 Dashboard Regime Badge
Update the SystemStatusPanel to show market regime when RegimeClassifier is active. Shows "UNKNOWN" in Phase 0 with no visual weight:

// In SystemStatusPanel.tsx — add to component list:
{ key: "market_regime", label: "Market Regime" }

// Regime color mapping (used when Phase 2 active):
const REGIME_COLORS: Record<MarketRegime, string> = {
TRENDING:      "text-profit",
RANGING:       "text-warning",
HIGH_VOLATILITY: "text-loss",
LOW_LIQUIDITY: "text-loss",
UNKNOWN:       "text-tertiary",  // Phase 0 — no visual weight
};

## 13.6 Analytics Page — Risk of Ruin Panel
Add a RiskOfRuinPanel component to the analytics page. Shows "insufficient data" in Phase 0, full calculation in Phase 2:

// components/analytics/RiskOfRuinPanel.tsx
"use client";
import type { RuinAnalysis } from "@/types/future";

interface Props { analysis: RuinAnalysis | null; }

export default function RiskOfRuinPanel({ analysis }: Props) {
if (!analysis || !analysis.is_sufficient) {
return (
<div className="bg-surface border border-border rounded-lg p-5">
<h3 className="text-card-title text-primary mb-2">Risk of Ruin</h3>
<p className="text-secondary text-sm">
Requires 20+ completed trades. {analysis?.sample_size ?? 0} trades so far.
</p>
</div>
);
}
// TODO Phase 2: render full probability display
return null;
}


# 14. Subagent Frontend Foundations
The subagent system requires new UI surfaces in the dashboard. All are stub pages/components in Phase 0.
## 14.1 New Pages Required
app/risk-monitor/page.tsx    # SA-03: Show thesis validity per open trade
app/onboarding/page.tsx      # SA-05: Conversational onboarding chat

// Both use ComingSoon component in Phase 0
// /intelligence page already planned (SA-04)
## 14.2 Risk Monitor Dashboard Panel
Add to open positions table: a thesis indicator column showing the last risk monitor assessment for each trade. Visible in Phase 2 when SA-03 is active.
// In OpenPositionsTable.tsx — add column:
{ key: "thesis", label: "Thesis" }

// Thesis cell rendering:
// thesis_valid=true  -> green dot "Valid"
// thesis_valid=false -> amber dot "Review" + tooltip with reasoning
// not checked yet   -> gray dash
## 14.3 Onboarding Chat Interface — Phase 3
// app/onboarding/page.tsx structure:
// Full-width chat interface (same pattern as /coach)
// Progress indicator: 4 steps (Capital | Experience | Risk | Confirm)
// Auto-applies settings on completion
// Redirects to /dashboard on complete

// API route: app/api/onboarding/route.ts
// POST body: { message: string, account_id: string }
// Calls SubagentOrchestrator.run_onboarding()
// Returns: { response: string, completed: boolean }
## 14.4 Analyst Briefing in Signal Detail
When SA-01 is active, the signal detail panel shows the analyst briefing above the AI reasoning section. In Phase 0 this section is hidden (empty briefing = section not rendered).
// In SignalDetailPanel.tsx — add section:
{signal.analyst_briefing && (
<Section title="Market Analysis">
<p className="text-secondary text-body-md">
{signal.analyst_briefing}
</p>
</Section>
)}
// Hidden when analyst_briefing is empty string — Phase 0 safe

| Attribute | Value |
|---|---|
| Document | Frontend Developer Specification (FDS) |
| Framework | Next.js 14 (App Router) |
| Language | TypeScript 5.4 — strict mode enabled |
| Styling | Tailwind CSS 3.4 + CSS custom properties |
| Data layer | Supabase JS client + Realtime subscriptions |
| Charts | Recharts (equity curve, analytics) |
| Design system | Custom — dark trading terminal aesthetic |
| Platform target | Web (desktop primary) + mobile responsive |
| Next document | DevOps Specification (Role 5) |


| Token | Value (Dark Theme) | Usage |
|---|---|---|
| --color-bg-primary | #0D1B2A | Main page background |
| --color-bg-surface | #111D2E | Cards, panels, sidebars |
| --color-bg-elevated | #1A2840 | Hover states, active panels |
| --color-bg-input | #0A1628 | Input fields, code areas |
| --color-border | #1E3050 | Default borders |
| --color-border-accent | #2A4070 | Emphasized borders |
| --color-text-primary | #E8F0FE | Primary text |
| --color-text-secondary | #8A9BC0 | Secondary / muted text |
| --color-text-tertiary | #4A5E80 | Disabled / placeholder |
| --color-accent | #3D8EFF | Brand blue — links, active states |
| --color-accent-glow | rgba(61,142,255,0.15) | Accent glow effects |
| --color-profit | #00C896 | Profit, BUY signals, positive P&L |
| --color-profit-dim | rgba(0,200,150,0.12) | Profit background tints |
| --color-loss | #FF4D6A | Loss, SELL signals, negative P&L |
| --color-loss-dim | rgba(255,77,106,0.12) | Loss background tints |
| --color-warning | #FFB347 | Warnings, CAUTIOUS state, news |
| --color-warning-dim | rgba(255,179,71,0.12) | Warning background tints |
| --color-hold | #8A9BC0 | HOLD signals, neutral states |
| --color-gold | #E67E22 | Brand gold — titles, premium features |
| --font-mono | 'JetBrains Mono', monospace | All prices, pips, numeric data |
| --font-sans | 'DM Sans', sans-serif | UI labels, headings, body text |
| --font-display | 'Space Grotesk', sans-serif | Page titles, large headings only |


| Role | CSS Class | Font / Size / Weight |
|---|---|---|
| Page title | text-display | Space Grotesk, 28px, 600 |
| Section heading | text-heading | DM Sans, 18px, 600 |
| Card title | text-card-title | DM Sans, 14px, 500 |
| Body text | text-body | DM Sans, 14px, 400 |
| Small label | text-label | DM Sans, 12px, 500, uppercase, tracking-wide |
| Price / numeric | text-price | JetBrains Mono, 16px, 500 |
| Large metric | text-metric | JetBrains Mono, 24px, 600 |
| Micro data | text-micro | JetBrains Mono, 11px, 400 |
| Code | text-code | JetBrains Mono, 13px, 400 |


| State / Value | Color Token | Components Using It |
|---|---|---|
| Positive P&L, WIN, profit | --color-profit (#00C896) | P&L numbers, outcome badges, equity curve |
| Negative P&L, LOSS, drawdown | --color-loss (#FF4D6A) | P&L numbers, outcome badges, drawdown overlay |
| BUY direction, long | --color-profit | Direction badges, signal cards, position rows |
| SELL direction, short | --color-loss | Direction badges, signal cards, position rows |
| HOLD signal | --color-hold | Signal cards action label |
| WARNING, CAUTIOUS risk state | --color-warning | Risk state badge, news alerts, approaching limits |
| System online / healthy | --color-profit | Status indicators, uptime dots |
| System degraded / error | --color-loss | Status indicators, circuit breaker |
| System warning | --color-warning | Status indicators, daily limit approaching |
| Confidence > 0.80 | --color-profit | Confidence bar fill |
| Confidence 0.65–0.79 | --color-warning | Confidence bar fill |
| Confidence < 0.65 | --color-loss | Confidence bar fill |


| Attribute | Specification |
|---|---|
| Width | 240px fixed (desktop). 64px icon-only (tablet < 1024px). Full-width overlay (mobile). |
| Background | --color-bg-surface with 1px right border (--color-border) |
| Logo area | LUMITRADE wordmark in Space Grotesk 600, gold color. Version badge beneath. |
| Nav items | Dashboard, Signals, Trades, Analytics, Settings. Active state: left border accent + bg-elevated fill. |
| Mode badge | Fixed at bottom. Shows PAPER (amber) or LIVE (profit green) badge. Pulsing dot animation when LIVE. |
| System dot | Colored dot showing system health: green = healthy, amber = degraded, red = offline. |
| Icons | Lucide React icon set. 18px, same color as text. |


| State | Content |
|---|---|
| Collapsed | Pair flag + name, BUY/SELL/HOLD badge with color, confidence bar (colored by level), timestamp, execution status, plain-English summary (2-4 sentences). Click to expand. |
| Expanded | Everything above PLUS: Full AI reasoning text. Per-indicator table with values and directional arrows. Timeframe confluence bars (H4 / H1 / M15). Confidence adjustment breakdown table. Active news events at time of signal. Entry / SL / TP prices. Risk/reward ratio display. |
| Executed (trade taken) | Green left border. "EXECUTED" badge. Links to corresponding trade record. |
| Rejected | Red left border. "REJECTED" badge. Shows rejection reason. |
| HOLD | Gray styling. "HOLD" badge. Collapsed only — no detail panel needed. |
| Rule-based fallback | Amber left border. "RULE-BASED" badge instead of AI badge. |


| Order | Component / File | Depends On | Priority |
|---|---|---|---|
| 1 | types/trading.ts + types/system.ts | Nothing | Critical |
| 2 | lib/formatters.ts | Nothing | Critical |
| 3 | lib/supabase.ts | env vars | Critical |
| 4 | hooks/useRealtime.ts | supabase.ts | Critical |
| 5 | ui/StatusDot.tsx | Nothing | High |
| 6 | ui/Badge.tsx | Nothing | High |
| 7 | ui/PnlDisplay.tsx | formatters.ts | High |
| 8 | ui/PriceDisplay.tsx | formatters.ts | High |
| 9 | hooks/useSystemStatus.ts | Nothing | High |
| 10 | layout/Sidebar.tsx | useSystemStatus, StatusDot | High |
| 11 | layout/TopBar.tsx | useSystemStatus, formatters | High |
| 12 | app/layout.tsx | Sidebar, TopBar | Critical |
| 13 | signals/ConfidenceBar.tsx | Nothing | High |
| 14 | signals/TimeframeScores.tsx | Nothing | High |
| 15 | signals/SignalDetailPanel.tsx | formatters, types | High |
| 16 | signals/SignalCard.tsx | DetailPanel, Badge, ConfidenceBar | High |
| 17 | hooks/useSignals.ts | useRealtime, types | High |
| 18 | signals/SignalFeed.tsx | useSignals, SignalCard | High |
| 19 | hooks/useOpenPositions.ts | useRealtime, types | High |
| 20 | dashboard/OpenPositionsTable.tsx | useOpenPositions, formatters | High |
| 21 | dashboard/AccountPanel.tsx | formatters, api | High |
| 22 | dashboard/TodayPanel.tsx | formatters, api | High |
| 23 | dashboard/SystemStatusPanel.tsx | useSystemStatus, StatusDot | High |
| 24 | dashboard/KillSwitchButton.tsx | Nothing | Critical |
| 25 | app/dashboard/page.tsx | All dashboard components | Critical |
| 26 | api/account/route.ts | supabase server | Critical |
| 27 | api/positions/route.ts | supabase server | Critical |
| 28 | api/signals/route.ts | supabase server | Critical |
| 29 | api/control/kill-switch/route.ts | supabase server | Critical |
| 30 | analytics/EquityCurve.tsx | recharts, types | High |
| 31 | analytics/MetricsGrid.tsx | types | High |
| 32 | app/analytics/page.tsx | analytics components | High |
| 33 | trades/TradeHistoryTable.tsx | formatters, types | Medium |
| 34 | app/trades/page.tsx | TradeHistoryTable | Medium |
| 35 | settings/* components | Nothing | Medium |
| 36 | app/settings/page.tsx | settings components | Medium |


| Attribute | Value |
|---|---|
| Version | 2.0 — 8 new page stubs, extended navigation, TypeScript types for all features |
| New pages | 8 stub pages (journal, coach, intelligence, marketplace, backtest, copy, analytics+, settings+) |
| Behavioral change | Zero — all stub pages show "coming soon" in Phase 0 |
| Type coverage | TypeScript interfaces for all 15 future features added to types/ |
