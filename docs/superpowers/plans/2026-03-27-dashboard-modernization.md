# Dashboard Modernization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernize all dashboard components with framer-motion animations, premium design, and light/dark mode support using CSS variables.

**Architecture:** Each panel gets motion.div wrappers for entrance animations, animated number counters, micro-interactions on hover, and staggered reveals. All colors use CSS variables for automatic dark/light mode.

**Tech Stack:** motion/react (framer-motion v12), lucide-react icons, CSS custom properties, existing glass morphism system

---

### Task 1: AccountPanel — Animated counters + hover effects

**Files:**
- Modify: `frontend/src/components/dashboard/AccountPanel.tsx`

- [ ] Replace static numbers with animated counters using motion
- [ ] Add entrance animation (fade up + scale)
- [ ] Add subtle hover lift on the panel
- [ ] Animated trend arrows for P&L changes
- [ ] Pulsing dot next to trading mode

### Task 2: TodayPanel — Large animated P&L + sparkline feel

**Files:**
- Modify: `frontend/src/components/dashboard/TodayPanel.tsx`

- [ ] Animated P&L number that counts up/down on data change
- [ ] Entrance animation with stagger for sub-metrics
- [ ] Color flash on P&L sign change
- [ ] Animated progress ring for win rate

### Task 3: SystemStatusPanel — Animated status dots + component cards

**Files:**
- Modify: `frontend/src/components/dashboard/SystemStatusPanel.tsx`

- [ ] Animated pulse dots per component (like 21.dev Status)
- [ ] Staggered entrance for each status row
- [ ] Animated latency numbers
- [ ] Status badge with color transition on change
- [ ] Uptime counter with animated numbers

### Task 4: OpenPositionsTable — Row animations + P&L flash

**Files:**
- Modify: `frontend/src/components/dashboard/OpenPositionsTable.tsx`

- [ ] AnimatePresence for row enter/exit
- [ ] P&L cells flash on value change
- [ ] Direction badges with micro-animation
- [ ] Hover row highlight with subtle scale
- [ ] Empty state with animated icon

### Task 5: Sidebar — Smooth collapse + active indicator

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`

- [ ] Animated width transition with motion
- [ ] Active nav item with animated left border (spring)
- [ ] Hover effects on nav items
- [ ] Animated logo transition (full → icon)
- [ ] Status section with animated dots

### Task 6: TopBar — Micro-interactions

**Files:**
- Modify: `frontend/src/components/layout/TopBar.tsx`

- [ ] Animated mode badge (pulse on LIVE)
- [ ] Clock with smooth number transitions
- [ ] Theme toggle with rotation animation

### Task 7: Dashboard Page Layout — Staggered grid entrance

**Files:**
- Modify: `frontend/src/app/(dashboard)/dashboard/page.tsx`

- [ ] Staggered entrance animation for grid panels
- [ ] Each panel fades in with slight delay
