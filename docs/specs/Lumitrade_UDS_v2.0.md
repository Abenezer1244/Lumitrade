



LUMITRADE
UI/UX Design Specification

ROLE 7 — SENIOR UI/UX DEVELOPER
Version 1.0  |  Wireframes · User Flows · Interaction Patterns · Accessibility
Classification: Confidential
Date: March 20, 2026




# 1. UX Philosophy & Design Goals
## 1.1 Core UX Principles
The Lumitrade dashboard is a professional monitoring and control interface for a live financial system. Every design decision is evaluated against three questions:

- Can the operator understand the system state in under 5 seconds without reading any text?
- Does every interaction have clear, unambiguous feedback within 200ms?
- Can the operator take emergency action (kill switch) in under 10 seconds from any page?


## 1.2 Primary User Tasks (by frequency)

# 2. Information Architecture
## 2.1 Site Map

## 2.2 Navigation Hierarchy
Navigation is flat — maximum one level deep. Every page is reachable from the sidebar in one click. No nested menus, no dropdowns, no hamburger menus on desktop.


# 3. Page Wireframes & Layout Specifications
## 3.1 Dashboard Page — Layout Specification
The dashboard is the operator's primary view. It must answer: "Is the system healthy? What happened today? What is open right now?" — all in one screen without scrolling on a 1080p display.

┌─────────────────────────────────────────────────────────────────────┐
│ SIDEBAR (240px fixed)   │  MAIN CONTENT (fills remaining width)     │
│                         │                                           │
│  LUMITRADE              │  Dashboard                          [mode]│
│  v1.0 · Phase 0         │                                           │
│                         │  ┌──────────────┐ ┌──────────┐ ┌───────┐ │
│  ● Dashboard   ◄active  │  │ ACCOUNT      │ │ TODAY    │ │SYSTEM │ │
│  ○ Signals              │  │              │ │          │ │STATUS │ │
│  ○ Trades               │  │ $312.45      │ │+$4.23    │ │       │ │
│  ○ Analytics            │  │ equity       │ │3 trades  │ │● AI   │ │
│  ○ Settings             │  │ $316.68      │ │67% WR    │ │● Feed │ │
│                         │  └──────────────┘ └──────────┘ │● OANDA│ │
│  ─────────────────      │                                 └───────┘ │
│  ● PAPER MODE           │  ┌──────────────────────┐ ┌────────────┐ │
│  ● All systems online   │  │ OPEN POSITIONS (3/5) │ │ SIGNALS    │ │
│                         │  │                      │ │            │ │
│                         │  │ EUR/USD BUY  +8.2p   │ │ 14:32 BUY  │ │
│                         │  │ GBP/USD SELL +3.1p   │ │ 82% ✓      │ │
│                         │  │ USD/JPY BUY  -1.4p   │ │            │ │
│                         │  │                      │ │ 13:15 SELL │ │
│                         │  └──────────────────────┘ │ 78% ✓      │ │
│                         │                            │            │ │
│                         │  [Emergency Halt]          │ 12:00 HOLD │ │
│                         │                            │ 54%        │ │
│                         │                            └────────────┘ │
└─────────────────────────────────────────────────────────────────────┘


## 3.2 Signals Page — Layout Specification
┌─────────────────────────────────────────────────────────────────────┐
│ SIDEBAR       │  Signals                    [Filters] [8 signals]  │
│               │                                                     │
│               │  ┌─ Filter Bar ──────────────────────────────────┐ │
│               │  │ Pair: [All ▼]  Action: [All ▼]  Date: [Today] │ │
│               │  └───────────────────────────────────────────────┘ │
│               │                                                     │
│               │  ┌─ Signal Card (collapsed) ─────────────────────┐ │
│               │  │ EUR/USD  [BUY]  ████████░░ 82%  ✓ EXECUTED    │ │
│               │  │ "EUR/USD shows bullish confluence across all   │ │
│               │  │  timeframes. RSI reversing from oversold..."   │ │
│               │  │                               14:32  [expand ▼]│ │
│               │  └───────────────────────────────────────────────┘ │
│               │                                                     │
│               │  ┌─ Signal Card (expanded) ──────────────────────┐ │
│               │  │ GBP/USD  [SELL] ███████░░░ 76%  ✗ REJECTED    │ │
│               │  │ "GBP/USD price approaching resistance..."      │ │
│               │  │                               13:15  [shrink ▲]│ │
│               │  │ ┌─Entry──┐  ┌─Stop Loss─┐  ┌─Take Profit─┐  │ │
│               │  │ │1.26540 │  │  1.26840  │  │   1.25940   │  │ │
│               │  │ └────────┘  └───────────┘  └─────────────┘  │ │
│               │  │ R:R  2.00:1    Spread at signal: 1.4 pips    │ │
│               │  │                                               │ │
│               │  │ Timeframe Confluence                          │ │
│               │  │ H4  ████████░░  82%                           │ │
│               │  │ H1  ███████░░░  74%                           │ │
│               │  │ M15 ██████░░░░  61%                           │ │
│               │  │                                               │ │
│               │  │ Indicators: RSI 34.2 ↑  MACD +0.00012 ↑     │ │
│               │  │             EMA20>EMA50>EMA200 ✓              │ │
│               │  │                                               │ │
│               │  │ AI Reasoning:                                 │ │
│               │  │ "The H4 timeframe shows price trading above   │ │
│               │  │  all three EMAs with RSI at 34.2, indicating  │ │
│               │  │  oversold conditions in an overall uptrend..." │ │
│               │  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘

## 3.3 Analytics Page — Layout Specification
┌─────────────────────────────────────────────────────────────────────┐
│ SIDEBAR       │  Analytics          [1D][1W][1M][3M][All]          │
│               │                                                     │
│               │  ┌─ Metrics Grid (2×4) ────────────────────────┐  │
│               │  │ Win Rate  Profit Fac  Sharpe   Max DD        │  │
│               │  │  67.3%      1.84       1.21    -3.2%         │  │
│               │  │  [green]   [green]    [green]  [green]       │  │
│               │  │                                               │  │
│               │  │ Avg Win   Avg Loss   Trades   Expectancy     │  │
│               │  │ +18.2p    -9.8p       45      +$1.24         │  │
│               │  └───────────────────────────────────────────────┘  │
│               │                                                     │
│               │  ┌─ Equity Curve ─────────────────────────────┐   │
│               │  │                           ╭──╮              │   │
│               │  │               ╭──╮       ╯  ╰──╮           │   │
│               │  │          ╭───╯  ╰──╮          ╰─           │   │
│               │  │  ───────╯                                   │   │
│               │  │  $300  Mar 7   Mar 10   Mar 14   Mar 20     │   │
│               │  └────────────────────────────────────────────┘   │
│               │                                                     │
│               │  ┌─ Pair Breakdown ──┐  ┌─ Session Breakdown ───┐  │
│               │  │ EUR/USD  67%  +24p│  │ OVERLAP  72%  best    │  │
│               │  │ GBP/USD  55%  +8p │  │ LONDON   61%          │  │
│               │  │ USD/JPY  50%  -2p │  │ NEW YORK 54%          │  │
│               │  └───────────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

## 3.4 Settings Page — Layout Specification
┌─────────────────────────────────────────────────────────────────────┐
│ SIDEBAR       │  Settings                                          │
│               │                                                     │
│               │  ┌─ Trading Mode ──────────────────────────────┐  │
│               │  │  ○ Paper Trading (Recommended for testing)   │  │
│               │  │  ○ Live Trading   [CONFIRM before switching] │  │
│               │  └─────────────────────────────────────────────┘  │
│               │                                                     │
│               │  ┌─ Risk Parameters ──────────────────────────┐   │
│               │  │  Max risk per trade    [─────●────] 1.0%    │   │
│               │  │  Daily loss limit      [──────●───] 5.0%    │   │
│               │  │  Weekly loss limit     [───────●──] 10.0%   │   │
│               │  │  Max open positions    [─●────────] 3       │   │
│               │  │  Min confidence        [────●─────] 65%     │   │
│               │  │  Max spread (pips)     [──●────────] 3.0    │   │
│               │  └────────────────────────────────────────────┘   │
│               │                                                     │
│               │  ┌─ Trading Parameters ───────────────────────┐   │
│               │  │  Pairs:  [EUR/USD ✓] [GBP/USD ✓] [USD/JPY ✓]  │
│               │  │  Scan interval:  [15 min ▼]                │   │
│               │  │  Trade cooldown: [60 min ▼]                │   │
│               │  │  Session filter: [London + NY overlap ▼]   │   │
│               │  └────────────────────────────────────────────┘   │
│               │                                                     │
│               │           [Save Changes]   [Reset to defaults]     │
└─────────────────────────────────────────────────────────────────────┘

# 4. Component Design Specifications
## 4.1 Status Indicators
Status indicators are the most important visual element in the dashboard. They must be immediately readable without hovering or clicking.


## 4.2 Data Display Components

## 4.3 Interactive Components

## 4.4 Empty States
Every list, table, and feed must have a designed empty state. Empty states are not errors — they are valid system states.


# 5. User Flow Specifications
## 5.1 Daily Morning Check Flow (< 30 seconds)
- User opens dashboard URL (browser remembers session)
- Dashboard loads — account panel shows balance and overnight P&L immediately
- User scans system status panel — all green = healthy, any amber/red = investigate
- User looks at open positions — any open from overnight? Current P&L?
- User checks today panel — any trades? Win rate so far?
- User glances at signal feed — last signal time and action
- If all looks normal: done in 30 seconds. If any anomaly: navigate to Signals or Trades for detail.

## 5.2 Signal Review Flow (< 1 minute)
- User navigates to Signals page
- User sees signal feed sorted by recency (newest first)
- User identifies signal of interest — pair, action, confidence visible in collapsed card
- User clicks card — expands to show full AI reasoning and indicators
- User reads plain-English summary (always first) then technical detail if desired
- User sees whether signal was executed or rejected (and why if rejected)
- If executed: user sees "EXECUTED" badge and can click to view the linked trade record
- User collapses card — returns to feed

## 5.3 Settings Update Flow (< 2 minutes)
- User navigates to Settings page
- User adjusts desired slider(s) — values update in real-time as slider moves
- All changes are staged — not yet saved
- User clicks "Save Changes" button
- Button shows loading spinner (200ms)
- On success: toast notification "Settings saved" appears bottom-right, auto-dismisses in 3 seconds
- On failure: error toast "Failed to save settings — please try again" with retry button
- Trading engine picks up new settings on next config refresh cycle (max 60 seconds)

## 5.4 Emergency Kill Switch Flow (< 10 seconds)
Design Priority  The kill switch must be activatable in under 10 seconds from any page. It must be impossible to activate accidentally. These two requirements are in tension — the solution is the two-step typed confirmation.

- User sees "Emergency Halt" text button (bottom of dashboard, always visible)
- User clicks button — a confirmation panel expands inline (no page navigation required)
- Panel shows: warning icon, explanation of consequences, text input field
- User types "HALT TRADING" in the text field (prevents accidental activation)
- "Activate Emergency Halt" button becomes enabled when text matches exactly
- User clicks "Activate Emergency Halt" button — loading state shown
- API call to /api/control/kill-switch completes
- Panel shows success state: "Emergency halt activated. All trading stopped."
- System status panel updates to show EMERGENCY_HALT state within 5 seconds
- SMS notification received confirming kill switch activation

## 5.5 Mode Switch Flow (Paper → Live)
- User navigates to Settings page
- User sees current mode badge (PAPER — amber)
- User clicks "Live Trading" radio option
- Confirmation modal appears: "Switch to Live Trading?" with three bullet points of consequences
- Modal requires user to check a checkbox: "I understand this will place real orders with real capital"
- User clicks "Switch to Live Trading" — modal closes, settings page shows LIVE badge
- Toast notification: "Mode switched to LIVE. Trades will use real capital."
- Trading engine picks up mode change within 60 seconds

## 5.6 Trade Detail Drill-Down Flow
- User is on Trades page viewing trade history table
- User clicks any trade row
- Trade detail slide-over panel appears from the right (does not navigate away from table)
- Panel shows: all trade fields, the originating signal (with summary), outcome, duration
- If trade has a linked signal: "View AI Signal" button opens signal expand panel within the slide-over
- User clicks X or clicks outside panel to close
- Returns to trade table at same scroll position

# 6. Micro-Interactions & Animation Specification
## 6.1 Animation Principles
- All animations serve a functional purpose — they communicate state change, not decoration.
- Duration: 100–200ms for UI feedback. 300ms for content reveals. Never exceed 400ms.
- Easing: ease-out for elements entering the screen. ease-in for elements leaving. ease-in-out for toggles.
- Respect prefers-reduced-motion: wrap all non-essential animations in the media query.
- Never animate color or opacity on financial data that updates frequently — it creates visual noise.

## 6.2 Animation Catalog

## 6.3 Reduced Motion Implementation
/* globals.css — respect user accessibility preference */
@media (prefers-reduced-motion: reduce) {
*,
*::before,
*::after {
animation-duration: 0.01ms !important;
animation-iteration-count: 1 !important;
transition-duration: 0.01ms !important;
}
.animate-pulse {
animation: none !important;
}
}

# 7. Responsive Design Specification
## 7.1 Breakpoint System

## 7.2 Component Behavior at Each Breakpoint

## 7.3 Touch Target Requirements
For mobile and tablet users, all interactive elements must meet minimum touch target sizes:

- Minimum touch target: 44×44px (Apple HIG standard)
- Signal cards: full card width tap target for expand — no small tap zone
- Navigation items: full sidebar width, 44px height minimum
- Table rows: 48px height minimum on mobile for easy tapping
- Sliders: 44px thumb target, 8px track with increased touch area
- Kill switch: 48px height minimum, intentionally sized to require deliberate tap

# 8. Accessibility Specification (WCAG 2.1 AA)
## 8.1 Color & Contrast Requirements
Color-only information  Profit/loss is communicated by color AND by sign (+ or -) AND by the text label (WIN/LOSS). Never rely on color alone to convey state. Screen reader users must receive the same information.

## 8.2 Keyboard Navigation

## 8.3 Screen Reader Requirements
- All status dots have aria-label describing the state: aria-label="AI Brain: online"
- Signal cards have aria-expanded="true/false" and aria-label="EUR/USD BUY signal, 82% confidence"
- P&L values include the sign in the accessible text: aria-label="positive four dollars and twenty-three cents"
- Live mode pulsing animation has aria-label="Live trading mode active" and role="status"
- Kill switch button has aria-label="Emergency halt — stop all trading"
- All tables have proper thead, th scope="col", and caption elements
- Loading states use aria-busy="true" and aria-live="polite"
- Toast notifications use role="alert" for immediate announcement by screen readers

## 8.4 Focus Management
- When signal card expands: focus moves to first interactive element within the detail panel
- When modal opens: focus traps within modal. When modal closes: focus returns to trigger element.
- When kill switch panel opens: focus moves to the text input field automatically
- After form save: focus moves to the success/error toast
- Skip-to-main-content link as first focusable element on every page

# 9. Loading States & Error Handling
## 9.1 Loading States

## 9.2 Skeleton Screen Implementation
// components/ui/Skeleton.tsx
"use client";

interface Props {
className?: string;
lines?: number;
}

export function Skeleton({ className = "" }: { className?: string }) {
return (
<div className={`
animate-pulse bg-elevated rounded
${className}
`} />
);
}

export function AccountPanelSkeleton() {
return (
<div className="bg-surface border border-border rounded-lg p-5">
<Skeleton className="h-4 w-24 mb-4" />
<Skeleton className="h-8 w-32 mb-2" />
<Skeleton className="h-4 w-20 mb-3" />
<div className="flex gap-4">
<Skeleton className="h-4 w-16" />
<Skeleton className="h-4 w-16" />
</div>
</div>
);
}

export function SignalCardSkeleton() {
return (
<div className="bg-surface border border-border rounded-lg p-4">
<div className="flex items-start gap-3 mb-3">
<Skeleton className="h-5 w-20" />
<Skeleton className="h-5 w-12" />
<Skeleton className="h-5 w-16 ml-auto" />
</div>
<Skeleton className="h-3 w-full mb-1" />
<Skeleton className="h-3 w-3/4 mb-3" />
<Skeleton className="h-2 w-full rounded-full" />
</div>
);
}

## 9.3 Error States

## 9.4 Toast Notification System
// components/ui/Toast.tsx — Implementation spec
// Position: fixed, bottom-right, 16px from edges
// Stack: multiple toasts stack vertically, newest on top
// Max visible: 3 toasts simultaneously
// Auto-dismiss: SUCCESS after 3s, INFO after 5s, ERROR persists until dismissed
// Manual dismiss: X button on each toast

type ToastType = "success" | "error" | "info" | "warning";

interface Toast {
id: string;
type: ToastType;
message: string;
action?: { label: string; onClick: () => void };
autoDismiss: boolean;
}

// Color mapping:
// success → green border + profit text
// error   → red border + loss text + persists
// warning → amber border + warning text
// info    → accent border + primary text

# 10. Complete Design Token Reference
## 10.1 Spacing & Sizing Tokens

## 10.2 Typography Tokens



END OF DOCUMENT
Lumitrade UI/UX Design Specification v1.0  |  Confidential
Next Document: QA Testing Specification (Role 8)





LUMITRADE
UI/UX Design Specification

ROLE 7 — SENIOR UI/UX DEVELOPER
All original design system + future feature UX patterns
Version 2.0  |  Includes future feature foundations
Date: March 21, 2026




# 1–10. All Original UDS Sections
All original UI/UX Design Specification content is unchanged: UX philosophy, information architecture, page wireframes, component specifications, user flows, micro-interactions, responsive design, accessibility, loading states, and design tokens.
Reference  Original UDS v1.0 is the authoritative source for all Phase 0 UI/UX. This document adds Section 11 only.

# 11. Future Feature UX Specifications
## 11.1 Updated Information Architecture
The navigation expands to include future pages. Phase indicator badges communicate what is available now vs later:


## 11.2 Dashboard Additions — Phase 2
### Market Regime Badge
Add to SystemStatusPanel, below the 6 component status rows. Uses semantic color to communicate regime at a glance:

// Regime badge — placed in SystemStatusPanel
// Phase 0: shows "UNKNOWN" in tertiary text (low visual weight)
// Phase 2: shows actual regime with semantic color

const REGIME_CONFIG = {
TRENDING:       { label: "Trending",       color: "text-profit",   bg: "bg-profit-dim"  },
RANGING:        { label: "Ranging",        color: "text-warning",  bg: "bg-warning-dim" },
HIGH_VOLATILITY:{ label: "High Volatility",color: "text-loss",     bg: "bg-loss-dim"    },
LOW_LIQUIDITY:  { label: "Low Liquidity",  color: "text-loss",     bg: "bg-loss-dim"    },
UNKNOWN:        { label: "—",              color: "text-tertiary", bg: ""               },
};

### Risk of Ruin Panel — Analytics Page
Add below the metrics grid in /analytics. Shows "insufficient data" message until 20+ trades, then full probability display:

ROR Panel layout (Phase 2):
┌─────────────────────────────────────────┐
│ Risk of Ruin Analysis              [?]  │
│                                         │
│ Lose 25% of account:    8.3%  [safe]   │
│ Lose 50% of account:    0.9%  [safe]   │
│ Lose 100% of account:   0.02% [safe]   │
│                                         │
│ ● STATUS: SAFE                          │
│ Based on last 52 trades                 │
└─────────────────────────────────────────┘

## 11.3 AI Coach Page UX — Phase 2
The coach page is a full-width conversational interface. The AI has context of all your trades and can answer questions about them.

┌──────────────────────────────────────────────────────┐
│ AI Trading Coach                                     │
│                                                      │
│ ┌──────────────────────────────────────────────────┐│
│ │ Coach: Hi! I have access to all your trade        ││
│ │ history. Ask me anything about your performance,  ││
│ │ a specific trade, or how to improve your settings.││
│ └──────────────────────────────────────────────────┘│
│                                                      │
│ ┌──────────────────────────────────────────────────┐│
│ │ You: Why did I lose on GBP/USD last Tuesday?      ││
│ └──────────────────────────────────────────────────┘│
│                                                      │
│ ┌──────────────────────────────────────────────────┐│
│ │ Coach: The GBP/USD SELL at 1.2654 on Tuesday     ││
│ │ hit its stop loss when UK manufacturing PMI...   ││
│ └──────────────────────────────────────────────────┘│
│                                                      │
│ Suggested questions:                                 │
│ [What was my best trade?] [Why did I win this week?] │
│ [Should I lower my risk?] [Which pair is best for me?]│
│                                                      │
│ ┌──────────────────────────────────────────┐ [Send] │
│ │ Ask anything about your trading...       │        │
│ └──────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────┘

## 11.4 Backtesting Studio UX — Phase 3
┌──────────────────────────────────────────────────────┐
│ Backtesting Studio                                   │
│                                                      │
│ Test configuration:                                  │
│ Pair:       [EUR/USD ▼]                             │
│ Date range: [Jan 2024] to [Mar 2026]                │
│ Min confidence: [────●────] 75%                     │
│ Risk per trade: [──●──────] 1.0%                    │
│                          [Run Backtest]              │
│                                                      │
│ Results vs Current Settings:                         │
│ ┌──────────────┬──────────────┬───────────────────┐ │
│ │ Metric       │ Test Config  │ Current Settings  │ │
│ │ Trades taken │ 284          │ 412               │ │
│ │ Win rate     │ 61%  [green] │ 52%               │ │
│ │ Total pips   │ +1,847       │ +1,203            │ │
│ │ Max drawdown │ -8.2%        │ -14.1%            │ │
│ │ Sharpe ratio │ 1.84         │ 1.21              │ │
│ └──────────────┴──────────────┴───────────────────┘ │
│                                                      │
│ [Apply test settings to live] [Save as template]    │
└──────────────────────────────────────────────────────┘


# 12. Subagent UX Specifications
The 5 subagents require new or updated UI surfaces. All follow the established Lumitrade design language: dark terminal aesthetic, semantic colors, progressive disclosure.
## 12.1 SA-01 Analyst Briefing — Signal Detail Panel Update
When SA-01 is active, an Analyst Briefing section appears above the AI Reasoning section in the expanded signal card. It shows the structured market analysis that informed the decision.
Signal card expanded layout (Phase 2 with SA-01 active):
┌─────────────────────────────────────────────────────┐
│ EUR/USD  [BUY]  ████████░░ 82%  ✓ EXECUTED         │
│                                                     │
│ MARKET ANALYSIS (by Analyst Agent)                  │
│ "EUR/USD is in a confirmed uptrend on H4. Price     │
│  has pulled back to EMA20 support at 1.0831.        │
│  RSI at 34 and turning up on M15. Spread 1.1 pips.  │
│  Overall bias: BULLISH"                             │
│                                                     │
│ AI REASONING (Signal Decision Agent)                │
│ "Based on the analyst briefing, EUR/USD shows       │
│  strong confluence for a long entry..."             │
└─────────────────────────────────────────────────────┘
## 12.2 SA-03 Risk Monitor — Open Positions Panel Update
Each open position row gains a Thesis column showing the last risk monitor assessment. Color-coded: green = valid, amber = review, gray = not checked yet.
Open positions table (Phase 2 with SA-03 active):
┌──────────┬─────┬─────────┬──────────┬──────────────┐
│ Pair     │ Dir │ Live P&L│ Time Open│ Thesis       │
├──────────┼─────┼─────────┼──────────┼──────────────┤
│ EUR/USD  │ BUY │ +$4.20  │ 2h 15m   │ ● Valid      │
│ GBP/USD  │ SELL│ -$1.80  │ 45m      │ ⚠ Review     │
│ USD/JPY  │ BUY │ +$0.90  │ 10m      │ — Pending    │
└──────────┴─────┴─────────┴──────────┴──────────────┘
Clicking the amber Review badge expands the risk monitor reasoning inline below the row. No separate page required.
## 12.3 SA-04 Intelligence Report Page — /intelligence
┌──────────────────────────────────────────────────────┐
│ Intelligence Report    Week of March 17, 2026        │
│                          [< Previous] [Next >]       │
│                                                      │
│ MACRO ENVIRONMENT                                    │
│ The Federal Reserve held rates steady this week...   │
│                                                      │
│ KEY LEVELS NEXT WEEK                                 │
│ EUR/USD Support: 1.0780  Resistance: 1.0920         │
│ GBP/USD Support: 1.2580  Resistance: 1.2750         │
│                                                      │
│ ECONOMIC CALENDAR                                    │
│ Tue 08:30  US CPI           ████ HIGH IMPACT        │
│ Thu 07:45  ECB Decision      ████ HIGH IMPACT        │
│ Fri 08:30  US NFP            ████ HIGH IMPACT        │
│                                                      │
│ YOUR SYSTEM THIS WEEK                                │
│ Win rate: 61% | Settings aligned with macro: YES    │
└──────────────────────────────────────────────────────┘
## 12.4 SA-05 Onboarding Chat — /onboarding
┌──────────────────────────────────────────────────────┐
│ Welcome to Lumitrade                                 │
│                                                      │
│ Step 1 of 4: Capital                                 │
│ ● ○ ○ ○                                              │
│                                                      │
│ ┌────────────────────────────────────────────────┐  │
│ │ Assistant: Hi! I'm going to help you set up    │  │
│ │ Lumitrade in just a few questions.              │  │
│ │ First — how much capital are you starting with? │  │
│ └────────────────────────────────────────────────┘  │
│                                                      │
│ ┌──────────────────────────────────────┐ [Send]    │
│ │ Type your answer...                  │           │
│ └──────────────────────────────────────┘           │
│                                                      │
│ Quick replies: [$500] [$1,000] [$5,000] [Other]    │
└──────────────────────────────────────────────────────┘

| Attribute | Value |
|---|---|
| Document | UI/UX Design Specification (UDS) |
| Design approach | Information-dense trading terminal — clarity over decoration |
| Primary user | Abenezer (operator) — monitors live trading, reviews signals daily |
| Primary device | Desktop web browser (1440px+). Mobile responsive secondary. |
| Interaction model | Read-heavy dashboard with focused write interactions (settings, kill switch) |
| Accessibility target | WCAG 2.1 AA compliance |
| Next document | QA Testing Specification (Role 8) |


| UX Principle | How It Applies to Lumitrade |
|---|---|
| Clarity at a glance | Dashboard uses color coding, large metric displays, and status indicators so system health is understood instantly — no scanning required. |
| Progressive disclosure | Signal cards show summary first, expand to full detail on demand. Users see what they need, not everything at once. |
| Error prevention over error recovery | Kill switch requires two-step typed confirmation. Mode switches show confirmation dialogs. Destructive actions are never one-click. |
| Consistent mental models | Profit is always green. Loss is always red. Warning is always amber. These never deviate for any reason. |
| Feedback for every action | Every button click, form submit, and system state change produces immediate visual feedback. No silent failures. |
| Information hierarchy | Most critical information (system status, account equity, open positions) is always visible without scrolling. Secondary data requires navigation. |


| Frequency | Task | Time Budget |
|---|---|---|
| Daily (AM) | Check overnight performance — did system trade? P&L? Any issues? | < 30 seconds |
| Daily (PM) | Review daily performance email summary | < 2 minutes |
| As-needed | Review an AI signal — why did it trade or not trade? | < 1 minute |
| As-needed | Check open position — current P&L, entry, SL, TP | < 15 seconds |
| Weekly | Review analytics — win rate, equity curve, pair performance | < 5 minutes |
| Occasional | Adjust risk settings — change risk %, thresholds | < 2 minutes |
| Emergency | Activate kill switch — halt all trading immediately | < 10 seconds |


| Page / Route | Primary Content |
|---|---|
| /auth/login | Email + password login form. Lumitrade branding. No other content. |
| /dashboard | Account panel. Today summary. System status. Open positions. Recent signals (compact). Kill switch. |
| /signals | Full signal feed with expand/collapse. Filters (pair, date, action). Signal count badge. |
| /trades | Paginated trade history table. Filters (date, pair, outcome, mode). CSV export. Trade detail on row click. |
| /analytics | Equity curve chart. Metrics grid (8 KPIs). Pair breakdown table. Session breakdown table. Date range selector. |
| /settings | Risk parameters. Trading parameters. Mode toggle (Paper/Live). Alert preferences. |


| Navigation Element | Location / Behavior |
|---|---|
| Sidebar | Fixed left, 240px. Always visible on desktop. Icon-only at 768–1023px. Hidden (drawer) below 768px. |
| Active state | Left border accent + elevated background. Only one item active at a time. |
| Page title | H1 at top of main content area. Matches sidebar label. Never truncated. |
| Breadcrumbs | Not used. Flat navigation makes breadcrumbs unnecessary. |
| Back navigation | Browser back button. No custom back buttons needed. |
| Deep links | Every page and trade record has a stable URL. Signals link to trade records by ID. |


| Panel | Dimensions | Content Priority |
|---|---|---|
| Account Panel | ~33% width, 140px height | Balance (large metric), equity, margin used, open count |
| Today Panel | ~25% width, 140px height | Daily P&L (colored large metric), trade count, win rate |
| System Status Panel | ~30% width, 140px height | 6 component status dots with labels, risk state badge |
| Open Positions Table | ~60% width, 220px height | Pair, direction badge, size, entry, live P&L, SL/TP |
| Signal Feed (compact) | ~38% width, 220px height | Last 8 signals — pair, action badge, confidence, time, status |
| Kill Switch Button | bottom-right, subtle | Red-bordered text button. Requires confirmation to activate. |


| Component | Visual Design | States | Usage |
|---|---|---|---|
| StatusDot (small) | 8px circle, 1px glow ring when active | green/amber/red/gray | Sidebar system health, table row status |
| StatusDot (medium) | 12px circle with label right-aligned | green/amber/red | System status panel component rows |
| RiskStateBadge | Pill badge, monospace font, uppercase | NORMAL=green, CAUTIOUS=amber, DAILY_LIMIT=red, EMERGENCY=red+pulse | Risk engine state display |
| ModeBadge | Pill badge, pulsing dot when LIVE | PAPER=amber, LIVE=green+pulse | Sidebar footer, top bar |
| CircuitBreakerBadge | Pill badge | CLOSED=green, OPEN=red, HALF_OPEN=amber | System status panel |
| OutcomeBadge | Tiny pill, uppercase | WIN=green, LOSS=red, BREAKEVEN=gray | Trade history table rows |


| Component | Design Rules | Behavior |
|---|---|---|
| PnlDisplay | Always show sign (+ or -). Green for positive. Red for negative. Gray for zero. Monospace font. Larger font for primary metrics. | Value updates trigger a brief color pulse animation (150ms). |
| PriceDisplay | Monospace font always. 5 decimal places for non-JPY pairs. 3 for JPY pairs. No currency symbol. | No animation — prices change too frequently. Static display. |
| ConfidenceBar | Horizontal bar, full container width. Color: green >=80%, amber 65-79%, red <65%. Percentage label right-aligned. | Animate fill width on initial render only (300ms ease-out). |
| TimeframeScores | Three labeled bars: H4, H1, M15. Same color rules as ConfidenceBar. Weights shown as labels. | Static display. No animation. |
| DirectionBadge | BUY = green background, white text. SELL = red background, white text. Bold uppercase. Small pill. | No animation. Static semantic color. |
| PairLabel | Monospace font, medium weight. EUR_USD displayed as EUR/USD. Flag emoji optional (decorative only). | Static display. |


| Component | Design Rules | Interaction Pattern |
|---|---|---|
| Primary Button | Full background fill with brand color. White text. 8px border-radius. 40px height. Disabled = 30% opacity. | Hover: slight bg darken. Active: scale(0.98). Loading: spinner replaces text. |
| Destructive Button | Red border, red text, transparent bg. Full red bg on hover. Requires confirmation pattern. | Never execute on first click. Always show confirmation dialog or typed confirmation. |
| Toggle (Paper/Live) | Track with animated thumb. Amber=Paper, Green=Live. 32px×18px. Clear label. | Click shows confirmation modal before switching to Live. Instant for Paper. |
| Slider (risk settings) | Full-width track, branded thumb, value label. Min/max labels at ends. | Debounced value display (100ms). Save only on explicit "Save Changes" click. |
| Select/Dropdown | Match surface background. Border on focus. Native select element for simplicity. | Standard browser behavior. No custom dropdowns in Phase 0. |
| Text Input | Dark background input field. Border highlight on focus. Error state: red border + message below. | Validate on blur, not on keystroke. Show error message below field. |
| SignalCard (click) | Entire card is clickable for expand/collapse. Cursor pointer. Hover: border brightens. | Smooth height transition (200ms ease). HOLD cards are not expandable. |
| Table Row (click) | Hover: bg-elevated highlight. Cursor pointer on clickable rows. | Opens trade detail panel or navigates to trade detail page. |


| Context | Empty State Message | Supporting Action |
|---|---|---|
| Open positions table — no open trades | System is watching. No open positions right now. | None — informational only |
| Signal feed — no signals yet today | No signals generated yet today. Next scan in Xm. | None — show countdown if possible |
| Trade history — no trades in date range | No trades in this period. Try expanding the date range. | Button: Reset filters |
| Analytics — insufficient data | Not enough trade data yet. Analytics requires 10+ completed trades. | Link to Signals page |
| Signals — all filtered out | No signals match your current filters. | Button: Clear filters |


| Interaction | Animation | Duration | CSS |
|---|---|---|---|
| Signal card expand | Height transition from collapsed to expanded | 200ms ease-in-out | transition: height 200ms ease-in-out, opacity 200ms |
| New signal appears in feed | Fade in + slide down from top | 200ms ease-out | opacity 0→1, translateY(-8px)→0 |
| P&L value update | Brief color pulse (same color as value, lighter) | 150ms | background-color flash then fade |
| Button hover | Background color darken | 100ms ease | transition: background-color 100ms |
| Button active/press | Scale down slightly | 80ms ease | transform: scale(0.98) |
| Live mode badge pulse | Pulsing green dot animation | 1500ms infinite | @keyframes pulse opacity 1→0.4→1 |
| Toast notification appear | Slide up from bottom-right + fade in | 200ms ease-out | translateY(16px)→0, opacity 0→1 |
| Toast auto-dismiss | Fade out + slide down | 150ms ease-in | opacity 1→0, translateY(0)→8px |
| Confidence bar fill | Width transition on initial render only | 300ms ease-out | width transition once on mount |
| Status dot — degraded | Amber pulse animation | 2000ms infinite | @keyframes pulse, amber color |
| Modal appear | Fade in backdrop + scale up modal | 150ms ease-out | backdrop opacity 0→0.5, modal scale(0.97)→1 |
| Kill switch panel expand | Smooth height reveal | 200ms ease-out | max-height 0→auto with overflow hidden |


| Breakpoint | Width Range | Layout Behavior |
|---|---|---|
| Desktop (primary) | 1280px+ | Full sidebar (240px). 3-column top row. 5-column mid row. All panels visible. |
| Laptop | 1024–1279px | Full sidebar. 2-column top row (status panel moves below). 4-column mid row. |
| Tablet | 768–1023px | Icon-only sidebar (64px). Single column layout. Panels stack vertically. |
| Mobile | < 768px | Hamburger menu (drawer). Full-width single column. Reduced padding. Bottom nav optional. |


| Component | Desktop | Tablet / Mobile |
|---|---|---|
| Sidebar | 240px fixed, full labels | 64px icon-only (tablet), or drawer (mobile) |
| Account Panel | 1/3 width, horizontal layout | Full width, horizontal metric layout preserved |
| Open Positions Table | 3/5 of mid row width | Full width, horizontal scroll for columns |
| Signal Feed | 2/5 of mid row width | Full width, below positions table |
| Signal Card expanded | Full width of content area | Full width, touch-friendly tap targets (44px min) |
| Metrics Grid | 2 rows × 4 columns | 2 rows × 2 columns (stacks to 4 rows × 2 on mobile) |
| Equity Curve | Full width | Full width, reduced height (150px on mobile) |
| Trade History Table | Full width, all columns visible | Full width, horizontal scroll or column priority hiding |
| Settings Sliders | Two-column layout | Single column, full width sliders |
| Kill Switch | Bottom right of dashboard | Bottom of page, full width on mobile |


| Text Combination | Contrast Ratio | Passes AA? |
|---|---|---|
| Primary text (#E8F0FE) on bg-primary (#0D1B2A) | 12.8:1 | ✓ AAA |
| Secondary text (#8A9BC0) on bg-surface (#111D2E) | 5.2:1 | ✓ AA |
| Profit green (#00C896) on bg-surface (#111D2E) | 5.8:1 | ✓ AA |
| Loss red (#FF4D6A) on bg-surface (#111D2E) | 5.1:1 | ✓ AA |
| Warning amber (#FFB347) on bg-surface (#111D2E) | 6.9:1 | ✓ AA |
| Accent blue (#3D8EFF) on bg-surface (#111D2E) | 4.7:1 | ✓ AA |
| White (#FFFFFF) on header-bg (#1A5276) | 6.3:1 | ✓ AA |
| Tertiary text (#4A5E80) on bg-surface (#111D2E) | 3.1:1 | ✗ FAIL — use secondary text for body content only |


| Interaction | Keyboard Support Required |
|---|---|
| Page navigation | Tab between nav items. Enter/Space to activate. Arrow keys within nav groups. |
| Signal card expand | Enter or Space to expand/collapse when card has focus. |
| Table rows | Arrow keys to navigate rows. Enter to open detail panel. Escape to close. |
| Modal / confirmation dialog | Tab cycles within modal only (focus trap). Escape to dismiss. Enter to confirm. |
| Kill switch flow | Tab to button → Enter to open panel → Tab to input → Type → Tab to button → Enter. |
| Settings sliders | Arrow keys to adjust value. Home/End for min/max. |
| Form submission | Enter submits focused form. Escape cancels. |


| Context | Loading Pattern | Duration Expectation |
|---|---|---|
| Initial page load | Skeleton screens matching the layout shape of the content | < 2 seconds |
| Real-time data refresh | No loading state — seamless background update. Values update in place. | Continuous |
| Signal feed initial load | Skeleton cards (3–5 gray placeholder cards with shimmer animation) | < 1 second |
| Trade history pagination | Inline spinner in the table body. Table header remains visible. | < 1 second |
| Settings save | Button text replaces with spinner. Form remains interactive. | < 500ms |
| Kill switch activation | Button shows "Activating..." with spinner. Input disabled. | < 2 seconds |
| Analytics data load | Full-page skeleton: metric card placeholders + chart placeholder | < 2 seconds |


| Error Type | User-Facing Message | Recovery Action |
|---|---|---|
| Network error (API unreachable) | Unable to load data. Check your connection. | Retry button. Auto-retry every 30s. |
| Session expired | Your session has expired. Please log in again. | Redirect to login page automatically. |
| Kill switch API failure | Failed to activate emergency halt. Please try again immediately. | Large retry button. Also shows OANDA URL to close trades manually. |
| Settings save failure | Failed to save settings. Your changes were not applied. | Retry button. Changes remain staged in the form. |
| Supabase Realtime disconnect | Live data updates paused. Reconnecting... | Auto-reconnect attempt. Toast notification when restored. |
| Invalid form input | Field-level error messages below each invalid input. | Error clears when user corrects the value. |


| Token | Value | Usage |
|---|---|---|
| space-1 | 4px | Tight spacing within components |
| space-2 | 8px | Internal component padding (compact) |
| space-3 | 12px | Gap between related elements |
| space-4 | 16px | Standard gap between components |
| space-5 | 20px | Card internal padding |
| space-6 | 24px | Section spacing |
| space-8 | 32px | Large section gap |
| radius-sm | 4px | Small elements: badges, chips |
| radius-md | 6px | Inputs, buttons, smaller cards |
| radius-lg | 8px | Cards, panels (primary radius) |
| radius-xl | 12px | Modals, large cards |
| border-width | 1px | All borders (never 2px on containers) |
| height-input | 40px | All text inputs and selects |
| height-button | 40px | All buttons (consistent with inputs) |
| height-table-row | 52px | Desktop. 48px minimum on mobile. |
| sidebar-width | 240px | Fixed sidebar desktop width |
| topbar-height | 64px | Fixed top bar height if used |


| Token | Font / Size / Weight / Leading | Usage |
|---|---|---|
| text-display | Space Grotesk, 28px, 600, 1.2 | Page titles only |
| text-heading-lg | DM Sans, 22px, 600, 1.3 | Section headings |
| text-heading-md | DM Sans, 18px, 600, 1.3 | Card headings |
| text-heading-sm | DM Sans, 14px, 500, 1.4 | Card sub-headings |
| text-body-md | DM Sans, 14px, 400, 1.6 | Body text, descriptions |
| text-body-sm | DM Sans, 12px, 400, 1.5 | Secondary text, captions |
| text-label | DM Sans, 11px, 500, 1.0, uppercase, +0.08em tracking | ALL data labels, column headers |
| text-metric-xl | JetBrains Mono, 32px, 600, 1.0 | Hero metrics (account balance) |
| text-metric-lg | JetBrains Mono, 24px, 600, 1.0 | Secondary metrics |
| text-metric-md | JetBrains Mono, 18px, 500, 1.2 | Table cell numbers |
| text-metric-sm | JetBrains Mono, 14px, 500, 1.4 | Inline data values |
| text-micro | JetBrains Mono, 11px, 400, 1.3 | Timestamps, fine detail |
| text-code | JetBrains Mono, 13px, 400, 1.6 | AI reasoning text, raw data |


| Attribute | Value |
|---|---|
| Version | 2.0 — UX specs for all 15 future features |
| New pages | 8 future page UX specifications (journal, coach, marketplace, backtest, etc.) |
| Design language | Unchanged — same dark terminal aesthetic, same color semantics |
| New patterns | Regime badge, sentiment indicators, ROR panel, coach chat interface |


| Page | Phase |
|---|---|
| /dashboard | 0 |
| /signals | 0 |
| /trades | 0 |
| /analytics | 0 |
| /settings | 0 |
| /journal | 2 |
| /coach | 2 |
| /intelligence | 2 |
| /marketplace | 3 |
| /copy | 3 |
| /backtest | 3 |
| /api-keys | 3 |
