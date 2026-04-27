# Lumitrade Frontend UI/UX Audit

**Date**: 2026-03-28
**Auditor**: Claude Code (Full 6-Pillar Visual Audit)
**Scope**: All pages, components, layout, typography, color, animation, accessibility, mobile

---

## Grading Scale

| Grade | Meaning |
|-------|---------|
| 4 | Excellent — production-ready, premium feel |
| 3 | Good — solid foundation, minor polish needed |
| 2 | Needs Work — functional but noticeably generic or inconsistent |
| 1 | Poor — broken, inaccessible, or significantly below standard |

---

## Pillar 1: Layout & Spatial Design — Grade: 3

### What's Working
- 12-column asymmetric bento grid (5-4-3 top row, 8-4 bottom) creates visual hierarchy
- Sidebar collapse/expand with localStorage persistence
- Mobile responsive with hamburger menu + overlay
- `gap-5` (20px) spacing between cards provides breathing room

### Issues Found

| # | Issue | Severity | File | Fix |
|---|-------|----------|------|-----|
| L-01 | **Top row cards don't match height** — AccountPanel is taller than TodayPanel/SystemStatus, causing uneven bottom edges | Medium | dashboard/page.tsx | Add `h-full` to inner card divs or use `items-stretch` on grid |
| L-02 | **OpenPositionsTable has `rounded-xl` (12px)** while all other cards use `--card-radius` (16px) via `.glass` | Medium | OpenPositionsTable.tsx:191 | Replace `rounded-xl` with glass class or use `rounded-[16px]` |
| L-03 | **TopBar height mismatch** — `h-12` (48px) is tight; main content uses `pt-16` (64px) leaving a 16px gap of nothing | Low | TopBar.tsx:71, layout.tsx:38 | Match `pt-` to actual TopBar height + desired spacing |
| L-04 | **Sidebar bottom section has inconsistent padding** — `px-4 py-4` expanded vs `px-2 py-3` collapsed, different border style | Low | Sidebar.tsx:291 | Standardize padding proportions |
| L-05 | **SignalFeed compact mode has no visual differentiation** — same glass card style as everything else, no hierarchy | Low | SignalFeed.tsx | Consider slightly muted treatment for secondary feeds |
| L-06 | **No max-width constraint on dashboard** — on ultrawide monitors (2560px+), cards stretch excessively | Medium | layout.tsx | Add `max-w-[1600px] mx-auto` to main content |

---

## Pillar 2: Typography & Hierarchy — Grade: 3

### What's Working
- Clear type scale: text-display (28px), text-heading (18px), text-metric (24px), text-label (12px)
- JetBrains Mono for all numbers/prices — correct for financial data
- Space Grotesk for headings adds personality
- Satoshi for body text is clean and readable
- AccountPanel balance at 32px is appropriately dominant

### Issues Found

| # | Issue | Severity | File | Fix |
|---|-------|----------|------|-----|
| T-01 | **text-label is ALL CAPS everywhere** — overused, feels like shouting (ACCOUNT, UNREALIZED P&L, TRADES, WINS, etc.) | Medium | globals.css:90 | Use sentence case for most labels, reserve ALL CAPS for badges only |
| T-02 | **System Status component labels use `text-xs`** not `text-label` — inconsistent with other panels | Low | SystemStatusPanel.tsx:261 | Standardize to text-label or pick one approach |
| T-03 | **Trades page table headers are `text-[10px]`** while Positions table headers are also `text-[10px]`** — too small for column headers | Medium | trades/page.tsx, OpenPositionsTable.tsx | Use `text-xs` (12px) minimum for table headers |
| T-04 | **Settings page slider labels lack hierarchy** — description text same visual weight as label | Low | TradingSettings.tsx | Add font-weight difference between label (600) and description (400) |
| T-05 | **SignalCard confidence value is plain text** — no visual emphasis on the most important signal metric | Medium | SignalCard.tsx | Make confidence value bold mono with color coding |
| T-06 | **MissionControl event timestamps are `text-[10px]`** — borderline too small for quick scanning | Low | MissionControl.tsx:63 | Consider `text-[11px]` for timestamps |

---

## Pillar 3: Color & Visual Design — Grade: 3

### What's Working
- Semantic color system (profit=green, loss=red, warning=orange) is consistently applied
- Dark theme `#0D1B2A` background is professional and appropriate for trading
- Accent blue `#3D8EFF` provides good visual anchoring for interactive elements
- Glass morphism with `backdrop-filter: blur(16px)` gives depth
- Border radius now 16px — modern and soft
- Icon-in-box pattern standardized across panel headers

### Issues Found

| # | Issue | Severity | File | Fix |
|---|-------|----------|------|-----|
| C-01 | **Light mode exists but conflicts with CLAUDE.md** — "NO light mode" is specified in design system, yet ThemeToggle is visible in TopBar | High | TopBar.tsx:105, globals.css:43-75 | Remove ThemeToggle from TopBar, or hide it; keep light mode CSS for future |
| C-02 | **Glass border opacity inconsistency** — globals.css says `0.3` but some components use inline `1px solid var(--color-border)` which is `0.6` opacity (old value stale?) | Medium | Multiple files | Verify --color-border value matches intent after recent change |
| C-03 | **KillSwitch success state SVG** is a custom inline SVG instead of using lucide-react ShieldOff import that was added | Low | KillSwitchButton.tsx:51 | Replace custom SVG with `<ShieldOff>` from lucide import |
| C-04 | **No hover state differentiation on sidebar nav items** — active and hover both feel similar (brand-dim vs bg-elevated) | Low | Sidebar.tsx:188-193 | Add subtle scale or border-left on hover for non-active items |
| C-05 | **Positions table row borders use inline style** `1px solid var(--color-border)` — not using softer 0.3 opacity glass border | Low | OpenPositionsTable.tsx | Use a softer border color or `border-border` class |
| C-06 | **HOLD badge is bg-elevated text-secondary** — too invisible, doesn't communicate "no action" clearly enough | Low | Badge.tsx | Consider a neutral tint (blue-dim or gray-dim) |
| C-07 | **No focus-visible ring** on interactive elements — keyboard users can't see focus state | High | globals.css | Add `focus-visible:ring-2 focus-visible:ring-accent` utility |

---

## Pillar 4: Animation & Micro-Interactions — Grade: 3

### What's Working
- Framer Motion stagger animations on dashboard load
- AnimatedNumber with smooth interpolation for balance/P&L
- PnlCell flash on value change (green up, red down)
- Direction badge micro y-animation (subtle, not distracting)
- Win rate arc stroke animation with delay
- AnimatePresence on tab switching
- Row enter/exit animations on positions table

### Issues Found

| # | Issue | Severity | File | Fix |
|---|-------|----------|------|-----|
| A-01 | **Every card uses identical entrance animation** — `opacity: 0, y: 20 → opacity: 1, y: 0` with uniform timing. This was the #1 "generic AI" complaint | Medium | dashboard/page.tsx | Vary: hero cards slower with scale, supporting cards faster |
| A-02 | **No hover lift on cards** — inspiration dashboards show cards lifting subtly on hover | Medium | Multiple | Add `hover:translate-y-[-2px] hover:shadow-lg transition-all` to glass class |
| A-03 | **Sidebar pulsing status dot** runs forever at full opacity — distracting peripheral motion | Low | Sidebar.tsx:313-326 | Reduce glow intensity or make it subtle (0→3px instead of 0→6px) |
| A-04 | **SignalFeed has no entrance animation** — cards just appear | Low | SignalFeed.tsx | Wrap in motion.div with stagger |
| A-05 | **Settings sliders have no visual feedback on drag** — plain browser range input styling | Medium | TradingSettings.tsx | Custom slider thumb with accent color glow on drag |
| A-06 | **Toast auto-dismiss has no exit animation** — just disappears | Low | Toast.tsx | Add opacity fade-out before removal |

---

## Pillar 5: Accessibility — Grade: 2

### What's Working
- `aria-live="polite"` on AccountPanel and TodayPanel
- `aria-live="assertive"` on KillSwitch success state
- `role="alert"` on error states
- `prefers-reduced-motion` media query reduces all animations
- Keyboard escape closes mobile sidebar
- Semantic `<nav>`, `<header>`, `<main>` elements
- `tabIndex` and keyboard support on SignalCard

### Issues Found

| # | Issue | Severity | File | Fix |
|---|-------|----------|------|-----|
| AC-01 | **No skip-to-content link** — keyboard users must tab through entire sidebar | High | layout.tsx | Add `<a href="#main-content" class="sr-only focus:not-sr-only">Skip to content</a>` |
| AC-02 | **Color contrast on text-tertiary** — `#6B7280` on `#0D1B2A` is 4.0:1, fails WCAG AA for normal text (needs 4.5:1) | High | globals.css:23 | Lighten to `#8A94A6` or similar for 4.5:1+ ratio |
| AC-03 | **No focus-visible styles** on buttons, links, or interactive elements | High | globals.css | Add global `focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent` |
| AC-04 | **Tables lack `<caption>` elements** — screen readers can't describe table purpose | Medium | OpenPositionsTable.tsx, trades/page.tsx | Add `<caption className="sr-only">Open trading positions</caption>` |
| AC-05 | **NotificationCenter dropdown has no ARIA** — no `aria-haspopup`, `aria-expanded`, or focus trap | Medium | NotificationCenter.tsx | Add dropdown ARIA attributes and focus management |
| AC-06 | **Sidebar phase badges** ("P2", "P3") have no `aria-label` explaining meaning | Low | Sidebar.tsx:238-249 | Add `aria-label="Phase 2 - coming soon"` |
| AC-07 | **Win rate arc SVG text** uses `className="fill-current text-primary"` which may not inherit correctly in all screen readers | Low | TodayPanel.tsx | Add `aria-label` to SVG with readable value |
| AC-08 | **Range sliders** in settings have no `aria-valuemin`, `aria-valuemax`, `aria-valuenow` | Medium | TradingSettings.tsx | Add ARIA range attributes |

---

## Pillar 6: Mobile & Responsive — Grade: 2

### What's Working
- Sidebar converts to overlay on mobile with hamburger menu
- Grid collapses to single column on mobile
- `md:` and `lg:` breakpoints used for progressive enhancement
- Body scroll lock when mobile sidebar is open

### Issues Found

| # | Issue | Severity | File | Fix |
|---|-------|----------|------|-----|
| M-01 | **Positions table not responsive** — 8 columns on mobile cause horizontal scroll, no column prioritization | High | OpenPositionsTable.tsx | Hide SL/TP columns on mobile, stack pair+direction |
| M-02 | **Trades page table** has same issue — too many columns for mobile | High | trades/page.tsx | Responsive card layout on mobile instead of table |
| M-03 | **TopBar left padding** `pl-14` on mobile is for hamburger button — but cuts into page title on small screens | Medium | TopBar.tsx:71 | Adjust to `pl-12` or make title truncate |
| M-04 | **Settings sliders** are functional but thumb is only 16px — below 44px touch target minimum | Medium | globals.css:147-153 | Increase touch target to 44px with transparent hit area |
| M-05 | **MissionControl event feed** timestamps + agent tags + pair + message don't fit on mobile — truncation makes events unreadable | Medium | MissionControl.tsx | Stack timestamp above message on mobile, or hide pair badge |
| M-06 | **KillSwitch confirmation input** — typing "HALT TRADING" on mobile keyboard is awkward, no autocomplete help | Low | KillSwitchButton.tsx | Consider shorter confirmation phrase for mobile |
| M-07 | **No mobile-specific touch targets** — many buttons are smaller than 44x44px minimum | Medium | Multiple | Audit all interactive elements for 44px minimum |
| M-08 | **Analytics page** — 8 chart components stacked vertically on mobile with no prioritization or collapsing | Medium | analytics/page.tsx | Consider tabs or accordion for mobile analytics |

---

## Summary Scorecard

| Pillar | Grade | Key Issue |
|--------|-------|-----------|
| Layout & Spatial Design | **3** | Height mismatch between top row cards, no max-width |
| Typography & Hierarchy | **3** | Over-use of ALL CAPS labels, small table headers |
| Color & Visual Design | **3** | Light mode toggle shouldn't exist, focus states missing |
| Animation & Micro-Interactions | **3** | Uniform entrance animations, no hover card lift |
| Accessibility | **2** | No skip link, contrast fails on tertiary text, no focus-visible |
| Mobile & Responsive | **2** | Tables break on mobile, touch targets too small |

**Overall: 2.7 / 4.0**

---

## Priority Fix List (Top 10)

| Priority | Issue | Impact | Effort |
|----------|-------|--------|--------|
| 1 | AC-01: Add skip-to-content link | High | 5 min |
| 2 | AC-02: Fix text-tertiary contrast ratio | High | 5 min |
| 3 | AC-03: Add focus-visible styles globally | High | 10 min |
| 4 | C-01: Remove ThemeToggle from TopBar | High | 2 min |
| 5 | M-01: Make positions table mobile-responsive | High | 30 min |
| 6 | L-01: Fix top row card height alignment | Medium | 5 min |
| 7 | L-06: Add max-width constraint for ultrawide | Medium | 2 min |
| 8 | A-02: Add hover lift to glass cards | Medium | 5 min |
| 9 | L-02: Fix OpenPositionsTable border radius | Medium | 2 min |
| 10 | T-01: Reduce ALL CAPS overuse on labels | Medium | 15 min |

---

## Quick Wins (< 5 min each)

1. Add `items-stretch` to top row grid for equal height cards
2. Add `max-w-[1600px] mx-auto` to main content area
3. Remove `<ThemeToggle />` from TopBar
4. Change `--color-text-tertiary` to `#8A94A6` for contrast
5. Add `focus-visible:ring-2 ring-accent ring-offset-2 ring-offset-[#0D1B2A]` to global button/link styles
6. Add `<a href="#main-content" className="sr-only focus:not-sr-only ...">Skip to content</a>`
7. Change OpenPositionsTable container from `rounded-xl` to style with `--card-radius`
8. Add hover transition to `.glass` class: `transition: transform 0.15s, box-shadow 0.15s`
