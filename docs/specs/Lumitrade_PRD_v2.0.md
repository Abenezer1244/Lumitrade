



LUMITRADE
AI-Powered Forex Trading Platform


PRODUCT REQUIREMENTS DOCUMENT
Version 1.0  |  Phase 0: Forex MVP
Classification: Confidential
Date: March 20, 2026




# 1. Executive Summary
Lumitrade is an enterprise-grade, AI-powered forex trading platform that autonomously executes trades on behalf of its users using real-time market data, multi-timeframe technical analysis, and Claude AI-driven decision-making. The system is architected from day one as a production-quality SaaS product, initially deployed as a personal trading tool on OANDA forex markets, with a clear roadmap to expand into stocks, crypto, and options — and ultimately to scale into a multi-tenant commercial platform.

Lumitrade is not a toy, script, or prototype. Every architectural decision is made with enterprise reliability, security, auditability, and scalability in mind. The codebase built in Phase 0 becomes the foundation of the commercial product.


# 2. Problem Statement & Product Vision
## 2.1 The Problem
Retail forex traders face a set of deeply intertwined challenges that systematically erode their capital and their confidence:
- Emotion-driven decisions — Fear and greed override rational analysis in real-time market conditions. Studies indicate that over 70% of retail forex traders lose money, with emotional trading cited as the primary cause.
- Information overload — Traders must simultaneously monitor price action, multiple timeframes, economic calendars, technical indicators, and sentiment data. No human can process all inputs optimally at scale.
- Execution speed — Institutional traders operate with algorithmic execution in microseconds. Retail traders executing manually are structurally disadvantaged.
- Lack of discipline — Even traders with solid strategies fail to consistently apply their own rules. Automation enforces discipline mechanically.
- No affordable professional tooling — Institutional-grade automated trading infrastructure costs hundreds of thousands of dollars to build and maintain. Existing retail tools (MetaTrader EAs, basic bots) are fragile, inflexible, and opaque.
- Opacity of existing AI tools — Current AI trading tools do not explain their reasoning. Users cannot trust or learn from a black box.

## 2.2 The Vision
Lumitrade's vision is to democratize institutional-grade algorithmic trading for the retail market — giving every serious individual trader access to the same caliber of AI-driven analysis, execution precision, and risk management that hedge funds and proprietary trading desks have used for decades.

Where Lumitrade is uniquely differentiated:
- Explainable AI — Every trade decision comes with a plain-English summary AND a detailed technical breakdown, so users understand and trust the system.
- Enterprise reliability from day one — Built with circuit breakers, crash recovery, data validation, and failover redundancy from the first line of code.
- Modular architecture — Each component (data engine, AI brain, risk engine, execution engine) is independently testable, swappable, and scalable.
- Multi-market roadmap — Forex is the starting point. The architecture supports stocks, crypto, and options without a rewrite.
- Future SaaS — The personal trading tool IS the product. There is no throwaway prototype phase.

## 2.3 Mission Statement
Mission  To build the most reliable, transparent, and intelligent AI trading platform available to retail investors — one that earns trust through explainability, protects capital through disciplined risk management, and grows from a personal tool into a global SaaS product.

# 3. Goals & Success Metrics
## 3.1 Phase 0 Goals (Months 1–3)

## 3.2 Phase 1 SaaS Goals (Months 6–12)

## 3.3 Non-Goals (Phase 0)
The following are explicitly OUT OF SCOPE for Phase 0 and must not influence architectural decisions in ways that compromise delivery speed:
- Multi-user support or tenant isolation
- Stocks, crypto, or options markets
- Mobile native application
- Strategy marketplace or social trading
- Payment processing or subscription billing
- Regulatory filings or investment advisor registration
- White-label or API-as-a-service offering

# 4. User Personas
## 4.1 Phase 0 — Primary Persona

## 4.2 Phase 1+ — Target Market Personas
### Persona A: The Aspiring Active Trader

### Persona B: The Strategy Tester

# 5. User Stories & Acceptance Criteria
## 5.1 Core User Stories — Phase 0
### Epic 1: Account & Broker Setup

### Epic 2: AI Signal Generation

### Epic 3: Risk Management

### Epic 4: Trade Execution

### Epic 5: Dashboard & Monitoring

### Epic 6: System Reliability

# 6. Functional Requirements
## 6.1 Data Engine Requirements

## 6.2 AI Brain Requirements

## 6.3 Risk Engine Requirements

## 6.4 Execution Engine Requirements

## 6.5 Dashboard Requirements

# 7. Non-Functional Requirements
## 7.1 Performance

## 7.2 Reliability & Availability

## 7.3 Security

## 7.4 Scalability (Future-Proofing)
While Phase 0 is single-user, all design decisions must support future multi-tenant SaaS architecture without requiring a rewrite:
- All database tables include an account_id foreign key from day one
- All configuration is stored in database records, not hardcoded constants
- The AI brain, risk engine, and execution engine are stateless services that receive context as input
- No global mutable state — all state is persisted to and read from the database
- Service boundaries are clearly defined, enabling future microservices decomposition

## 7.5 Observability
- All log entries are structured JSON with timestamp, level, component, event, data, and trace_id fields
- Every trade signal, decision, execution step, and outcome is logged as a separate, queryable record
- System health metrics (AI latency, API error rate, signal count, P&L) are exposed as structured data
- All risk events, circuit breaker trips, and safety filter activations are logged with full context
- A /health endpoint returns system status, component availability, and last heartbeat timestamp

# 8. Feature Specifications — MVP (v1.0)
## 8.1 Feature: Multi-Timeframe AI Signal Engine

## 8.2 Feature: Adaptive Risk Engine

## 8.3 Feature: Explainable AI Trade Dashboard

## 8.4 Feature: Paper Trading Mode

## 8.5 Feature: Trade History & Analytics

# 9. Feature Roadmap — V2 & V3
## 9.1 V2 Features (Months 4–8)

## 9.2 V3 Features (Months 9–18)

# 10. AI Brain — Deep Specification
## 10.1 Prompt Architecture
The AI brain uses a structured system prompt and a dynamically assembled user prompt. The system prompt defines the AI's role, constraints, and output format. The user prompt is constructed fresh for each signal scan with live market data.

### System Prompt (Static)
System Prompt Template  You are Lumitrade's professional forex trading analyst. Your role is to analyze multi-timeframe market data and generate high-probability trading signals with disciplined risk management. You MUST respond ONLY with valid JSON matching the exact schema provided. Never include prose outside the JSON. If market conditions do not support a clear directional bias, return action: HOLD. Prioritize capital preservation over opportunity. Never force a trade.

### User Prompt Components (Dynamic, assembled per scan)
- 1. Market context: current pair, current bid/ask, spread in pips, active trading session, UTC timestamp
- 2. Multi-timeframe candle data: last 50 candles each for M15, H1, H4 (OHLCV format)
- 3. Computed indicators: RSI(14), MACD(12,26,9) line/signal/histogram, EMA(20/50/200), ATR(14), BB upper/mid/lower
- 4. Economic calendar: any high or medium impact events in the next 4 hours for affected currencies
- 5. Recent system context: last 3 trades on this pair (outcome, direction, entry), current open positions, consecutive loss count
- 6. Risk context: current account balance, today's P&L, risk % to be used if signal confidence qualifies
- 7. Output schema: exact JSON structure required with field names, types, and constraints

## 10.2 AI Output Schema

## 10.3 Confidence Adjustment Pipeline
After receiving the AI confidence score, the system applies a multi-factor adjustment before any trading decision is made:

## 10.4 Validation Rules (all must pass before execution)
- Schema validation: all required fields present and correct types
- Action is valid enum value
- Confidence is float 0.0 <= confidence <= 1.0
- Entry price within 0.5% of live price at time of validation
- For BUY: stop_loss < entry_price AND take_profit > entry_price
- For SELL: stop_loss > entry_price AND take_profit < entry_price
- Risk/reward ratio >= 1.5 : (|entry − TP| / |entry − SL|)
- Adjusted confidence >= current threshold (default 0.65)
- No active news blackout window for either currency in the pair
- Current open positions < maximum allowed
- Pair not in cooldown period from recent trade
- Daily loss limit not reached
- Spread at time of validation < configured maximum
- Circuit breaker status = CLOSED

# 11. Risk Engine — Deep Specification
## 11.1 Position Sizing Algorithm
Position sizing is calculated dynamically on every trade. No fixed lot sizes are used.


## 11.2 Risk State Machine
The risk engine maintains a formal state machine that governs all trading permissions:

## 11.3 Order Safety Protocol
Before any order is submitted to OANDA, the execution engine performs the following safety checks in sequence. Any failure at any step aborts the order:
- Verify risk state is NORMAL or CAUTIOUS (not any halt/block state)
- Verify open position count < maximum allowed
- Verify pair is not in cooldown period
- Re-fetch live price and verify signal entry is still within 0.5% of current price
- Re-verify spread is within acceptable limit (price may have moved)
- Calculate final position size with current balance (balance may have changed)
- Verify calculated position size >= minimum (1,000 units)
- Acquire pair-level trade lock (prevent concurrent duplicate orders)
- Submit order — capture order ID immediately
- Verify fill within 2 seconds — query OANDA for order status
- Release trade lock
- Log all parameters and outcome to trades table
- Send alert notification

# 12. Data Architecture & Logging Specification
## 12.1 Database Schema Overview
All tables use UUID primary keys and include created_at / updated_at timestamps. All tables include account_id for future multi-tenant support.

### Table: accounts

### Table: trades

### Table: signals

### Additional Tables

## 12.2 Structured Log Format
Every log entry emitted by the system follows this JSON schema:
Log Schema  { "timestamp": "ISO-8601", "level": "DEBUG|INFO|WARNING|ERROR|CRITICAL", "component": "data_engine|ai_brain|risk_engine|execution_engine|dashboard|system", "event": "SNAKE_CASE_EVENT_NAME", "trace_id": "UUID per scan cycle", "data": { ...context-specific fields }, "duration_ms": optional }

# 13. Security & Compliance Specification
## 13.1 Threat Model

## 13.2 Secrets Management Protocol
- Development environment: .env file in project root. File is .gitignored. Never committed.
- Staging/Production (Railway): Environment variables set via Railway dashboard. Never in code.
- OANDA API keys: Two separate keys created — one read-only (data engine), one trading (execution engine only).
- Anthropic API key: Single key. Used only by AI brain module. Stored as env var.
- Supabase keys: Service role key for backend only. Anon key for dashboard (frontend) with RLS enforced.
- Key rotation schedule: All API keys rotated every 90 days. Documented rotation procedure with checklist.
- Key audit: Monthly review of all active API keys and their assigned permissions.

## 13.3 OANDA Account Hardening
- Enable IP whitelisting: Restrict API access to cloud server IP address only
- Create separate API keys for data access (read-only) and trade execution (trading permission only)
- Enable account activity alerts in OANDA portal for any login or configuration change
- Set OANDA account to require 2FA for web portal access
- Configure maximum leverage limits in OANDA account settings appropriate for account size

## 13.4 Regulatory Positioning
Legal Note  Lumitrade Phase 0 is a personal automation tool used by its creator for their own trading account. It does not constitute investment advice, portfolio management, or brokerage services. Future SaaS commercialization will require legal review of applicable regulations including SEC/FINRA (if US equities are added), CFTC rules for forex, and applicable state money transmission laws.


# 14. Technology Stack — Decision Record
## 14.1 Core Technology Decisions

## 14.2 Estimated Monthly Infrastructure Cost

# 15. Internal API Contracts
## 15.1 Data Engine → AI Brain Contract
The data engine produces a MarketSnapshot object passed to the AI brain on each scan cycle:
MarketSnapshot Schema  pair: str | session: str | timestamp: ISO-8601 | bid: float | ask: float | spread_pips: float | candles_m15: List[Candle] | candles_h1: List[Candle] | candles_h4: List[Candle] | indicators: IndicatorSet | news_events: List[NewsEvent] | recent_trades: List[TradeSummary] | account_context: AccountContext

## 15.2 AI Brain → Risk Engine Contract
The AI brain produces a SignalProposal passed to the risk engine for validation:
SignalProposal Schema  signal_id: UUID | pair: str | action: BUY|SELL|HOLD | confidence_raw: float | confidence_adjusted: float | entry_price: float | stop_loss: float | take_profit: float | summary: str | reasoning: str | timeframe_scores: dict | indicators_snapshot: dict | key_levels: list | generation_method: AI|RULE_BASED | created_at: ISO-8601

## 15.3 Risk Engine → Execution Engine Contract
The risk engine produces an ApprovedOrder only when all validation checks pass:
ApprovedOrder Schema  signal_id: UUID | pair: str | direction: BUY|SELL | units: int | entry_price: float | stop_loss: float | take_profit: float | risk_amount_usd: float | risk_pct: float | account_balance_at_approval: float | approved_at: ISO-8601 | expiry: ISO-8601 (30s from approval)

## 15.4 Dashboard API Endpoints

# 16. Constraints, Dependencies & Risk Register
## 16.1 Technical Constraints
- OANDA API rate limits: 100 requests per second. Signal scans must be designed to stay within limits.
- Anthropic API rate limits and costs: high-frequency scanning increases costs. Signal interval must balance quality with cost.
- Railway.app free tier: limited to 512MB RAM and shared CPU. Pro tier required for production.
- Supabase free tier: 500MB database, 2GB bandwidth. Sufficient for Phase 0. Monitor and upgrade before SaaS launch.
- OANDA minimum position size: 1,000 units. Position sizing algorithm must account for this floor.
- OANDA leverage restrictions: vary by jurisdiction and account type. Risk engine must respect leverage constraints.

## 16.2 Risk Register

# 17. Build Roadmap — Week by Week
## 17.1 Phase 0 Build Plan (13 Weeks)

# 18. Definition of Done & Acceptance Criteria
## 18.1 Phase 0 — Overall Acceptance Criteria
The Phase 0 system is considered complete and ready for live trading when ALL of the following criteria are met:

### System Reliability
- System runs continuously for 7 days without requiring manual intervention
- Crash recovery tested: process killed externally, auto-restarts within 60 seconds, position reconciliation correct
- Local failover tested: cloud process killed, local backup activates within 3 minutes automatically
- Kill switch tested: activates in < 10 seconds, closes all paper positions, halts all signals

### Data Integrity
- All five data validation checks execute on every tick with zero bypass
- Stale data test: price feed disconnected manually — system detects within 10s, logs event, halts signals
- Spike injection test: artificial price spike injected — system detects and rejects, trade not placed

### AI Quality
- Zero trades executed from an AI signal that failed schema validation
- All rejected signals logged with specific rejection reason
- Every executed trade has a corresponding AI summary and full reasoning in the database
- Fallback rule-based signal generation tested and confirmed working when Claude API is unavailable

### Risk Engine
- Daily loss limit test: simulate −5% daily P&L, confirm trading halts immediately
- Max positions test: 3 trades open, 4th signal generated, confirm 4th is rejected with correct reason
- News block test: high-impact event created in test calendar, confirm signals blocked in window
- Position sizing verified correct for 3 different account sizes and stop loss distances

### Trading Performance (Paper)
- Minimum 50 paper trades logged across all 3 currency pairs
- Win rate > 40% over 50+ trade sample (statistical minimum for live progression)
- No single paper trade loss exceeded 2% of account balance
- Daily loss limit never breached in paper trading period

### Dashboard
- All real-time data updates within 5 seconds of underlying change
- Trade history accurately matches database records — zero discrepancies in spot check of 20 trades
- Signal expand panel shows complete AI reasoning, all indicator values, and confluence scores for every signal
- CSV export produces clean, complete, accurate trade log

### Security
- Zero API keys present in any source code file or git history
- OANDA API key IP whitelist confirmed active and tested
- Log scrubber test: API key deliberately included in log message — confirm redacted in output
- GitHub repository scanned with gitleaks or equivalent — zero secrets detected

## 18.2 Go/No-Go Checklist for Live Capital



END OF DOCUMENT
Lumitrade PRD v1.0  |  Confidential  |  Abenezer — Founder
Next Document: System Architecture Specification (Role 2)





LUMITRADE
Product Requirements Document

ROLE 1 — SENIOR PRODUCT MANAGER
Phase 0: Forex MVP + Future Feature Foundations
Version 2.0  |  Includes future feature foundations
Date: March 21, 2026




# 1. Executive Summary
Lumitrade v2.0 extends the original PRD with foundations for 15 future features across four tiers. Every future feature has its database tables, interfaces, stub modules, and architectural hooks built during Phase 0 — so adding full functionality later requires filling in logic, not restructuring the system.

Version 2.0 change  All original PRD content is preserved and unchanged. This document adds Section 11 (Future Feature Specifications) and updates relevant existing sections to reference future hooks. The Phase 0 build scope is identical to v1.0.

# 2–10. All Original PRD Sections
Sections 2 through 10 are identical to PRD v1.0. Refer to the original document for: Problem Statement, Goals & Metrics, User Personas, User Stories, Functional Requirements, Non-Functional Requirements, Feature Specifications MVP, Feature Roadmap V2–V3, AI Brain Spec, Risk Engine Spec, Data Architecture, Security, Tech Stack, API Contracts, Constraints, Build Roadmap, and Acceptance Criteria.

Reference  All original content preserved. Only additions are documented below.

# 11. Future Feature Specifications
These 15 features are not built in Phase 0. Their foundations — database tables, stub classes, interface hooks, and prompt slots — ARE built in Phase 0. This section defines what each feature does, when to build it, and what the Phase 0 foundation provides.

## 11.1 Tier 1 — High Impact Features
### Feature F-01: Multi-Model AI Brain

### Feature F-02: Market Regime Detection

### Feature F-03: News Sentiment AI

### Feature F-04: Correlation Guard

### Feature F-05: Trade Journal AI

## 11.2 Tier 2 — Game-Changing Features
### Feature F-06: Strategy Marketplace

### Feature F-07: Copy Trading

### Feature F-08: AI Trading Coach

### Feature F-09: Multi-Asset Expansion

### Feature F-10: Native Mobile App

## 11.3 Tier 3 — Visionary Features
### Feature F-11: Lumitrade Intelligence Report

### Feature F-12: Risk of Ruin Calculator

### Feature F-13: Backtesting Studio

### Feature F-14: Public API + Webhooks

### Feature F-15: Lumitrade Fund

## 11.4 Future Feature Roadmap Summary


# 12. Self-Improvement and Adaptive Sizing (Phase 0 Foundations)
These two systems are documented in full in BDS Section 14 and 15. This section summarizes the product requirements.
## 12.1 Self-Improvement System
The system analyzes its own trade history and improves its AI prompts and risk rules over time. Phase 0 builds the data pipeline and stub modules. Phase 2 activates pattern detection at 50+ trades. Phase 3 adds prompt evolution at 500+ trades.
The feedback loop: trade closes -> post-trade analyzer fires -> findings stored in performance_insights table -> next signal prompt includes findings -> AI makes better decisions.
Three levels: (1) Rule Learning — system detects weak conditions and tightens filters. (2) Prompt Evolution — system improves its own AI prompts based on what reasoning predicted wins. (3) Model Fine-Tuning — at 10,000+ trades, fine-tune a custom model on Lumitrade trade data.
## 12.2 Adaptive Position Sizing
Phase 0 uses fixed confidence-to-risk mapping (0.65-0.79 = 0.5%, 0.80-0.89 = 1.0%, 0.90+ = 2.0%). Phase 2 allows Claude to recommend position size based on recent performance context (win rate, streaks, volatility, trend strength). Hard limits always enforced: 0.25% minimum, 2.0% maximum, regardless of AI recommendation.
The PerformanceContext dataclass carries recent trade statistics to every signal scan. PerformanceContextBuilder computes this from trade history. When sample_size >= 20, recommended_risk_pct in the AI response is used instead of the fixed table. Below 20 trades: always falls back to standard confidence-based sizing.

# 16. Subagent Architecture
Lumitrade uses five specialized AI subagents — separate Claude API calls that run in parallel or asynchronously alongside the main signal pipeline. Each subagent has a single focused job, a clean interface, and a Phase 0 stub that is a silent no-op until activated.
Design principle  No subagent ever blocks the main trading loop. Every subagent call is async, wrapped in try/except, and has a safe default if it fails or is not yet implemented.
## SA-01: Market Analyst Subagent
What it does: Before the Signal Decision Agent receives data, the Market Analyst reads raw OHLCV, indicator values, and recent price action and produces a structured plain-English briefing. The Signal Decision Agent reads this briefing instead of raw numbers, making cleaner and more accurate decisions.
Why it improves signals: The current single-prompt approach asks Claude to simultaneously parse raw indicator values AND make a trading decision. Separating analysis from decision-making reduces cognitive load, produces better decisions, and allows using a more powerful model for analysis and a faster model for decisions.
Output: A 200-400 word structured market briefing per pair per scan. Stored in signal record as analyst_briefing field.
Phase to build: Phase 2 — after 50+ live trades prove the single-model baseline.
Phase 0 foundation: MarketAnalystAgent stub class. analyst_briefing field on signals table. Prompt builder accepts briefing parameter (uses empty string in Phase 0).
## SA-02: Post-Trade Analyst Subagent
What it does: Fires asynchronously every time a trade closes. Reads the entry signal reasoning, all indicator values at entry, what the market did during and after the trade, and the outcome. Produces a finding about why the trade won or lost and one specific recommendation.
Why it matters: This is the learning engine. Without post-trade analysis, the system runs the same strategy forever. With it, the system discovers what conditions actually predict wins versus losses in real market data — not theory.
Output: Structured finding stored in performance_insights table. Feeds automatically into next signal prompt via the PERFORMANCE INSIGHTS slot.
Phase to build: Phase 2 — after 20+ live trades. The _trigger_insight_analysis hook already exists in ExecutionEngine.
Phase 0 foundation: PostTradeAnalystAgent stub class. _trigger_insight_analysis hook in ExecutionEngine (already built). performance_insights table (already built). analyze() method in PerformanceAnalyzer (already built as stub).
## SA-03: Risk Monitor Subagent
What it does: Runs every 30 minutes while any position is open. Reads current open positions, current market conditions, and recent price action since entry. Reasons about whether the original trade thesis still holds. If the thesis is invalidated, flags a recommendation to close early.
Why it matters: The current risk engine only exits at predefined stop loss and take profit prices. It cannot reason about market structure changes. A position opened on a support bounce should be reconsidered if price breaks decisively below that support — even if the numeric stop loss has not been hit yet.
Output: Reasoning stored in risk_monitor_log table. Recommendations surfaced on dashboard. Critical findings trigger immediate SMS alert.
Phase to build: Phase 2 — after live trading is established and stable.
Phase 0 foundation: RiskMonitorAgent stub class. risk_monitor_log table. 30-minute scheduler slot in main.py (does nothing until activated). Dashboard panel stub showing No active monitoring (Phase 2 feature).
## SA-04: Intelligence Subagent
What it does: Fires every Sunday at 19:00 EST. Orchestrates three sequential sub-calls: (1) News Analyst reads the week's major economic headlines and central bank communications. (2) Performance Analyst summarizes the week's trades, win rate, and patterns. (3) Intelligence Writer synthesizes both into a structured weekly briefing with macro context, key levels for the coming week, and how Lumitrade's current settings align with the macro environment.
Why it matters: This is the feature that justifies the subscription price to serious traders. A personalized weekly macro briefing tied to their actual trading pairs and system performance is genuinely valuable. It is what Bloomberg Terminal charges $24,000/year to provide.
Output: Stored in intelligence_reports table. Emailed via SendGrid. Viewable on /intelligence dashboard page.
Phase to build: Phase 2 — requires NEWS_API_KEY environment variable.
Phase 0 foundation: IntelligenceSubagent stub class (coordinates 3 sub-calls). Sunday 19:00 scheduler slot in main.py. intelligence_reports table (already built). /intelligence route stub in frontend.
## SA-05: Onboarding Subagent
What it does: When a new SaaS user signs up, instead of showing a static settings form, a conversational AI guides them through setup. It asks about their capital, risk tolerance, trading experience, and goals. Based on their answers, it recommends and automatically applies appropriate settings. It explains what will happen when the system starts trading.
Why it matters: Onboarding is the single highest-impact moment in a SaaS product. Users who understand what they signed up for have dramatically lower churn. An AI conversation that personalizes setup makes users feel confident rather than confused.
Output: Completed onboarding stored in onboarding_sessions table. Settings automatically configured. Welcome email sent. First signal scan scheduled.
Phase to build: Phase 3 — SaaS launch. Requires multi-user infrastructure.
Phase 0 foundation: OnboardingAgent stub class. onboarding_sessions table. /onboarding route stub in frontend. Settings auto-apply function (used by both manual settings and onboarding agent).
## SA Summary Table
Agent | Phase | Trigger | Blocks Main Loop | Phase 0 Cost
SA-01 Market Analyst | 2 | Every signal scan | No — runs before, feeds briefing | ~$0.002/scan
SA-02 Post-Trade Analyst | 2 | Every trade close | No — fully async | ~$0.003/trade
SA-03 Risk Monitor | 2 | Every 30 min w/ open positions | No — async | ~$0.002/fire
SA-04 Intelligence | 2 | Sunday 19:00 EST | No — weekly batch | ~$0.02/week
SA-05 Onboarding | 3 | New user signup | No — user-facing | ~$0.01/user

| Document Owner | Abenezer — Founder, Lumitrade |
|---|---|
| Document Type | Product Requirements Document (PRD) |
| Current Phase | Phase 0 — Personal MVP (OANDA Forex) |
| Target Platform | Web (primary) + Native Mobile (later) |
| Next Phase | Multi-market SaaS (Stocks, Crypto, Options) |


| Attribute | Value |
|---|---|
| Product Name | Lumitrade |
| Phase | Phase 0 — Personal Forex MVP |
| Primary Broker | OANDA (fxTrade) |
| Primary Market | Forex (EUR/USD, GBP/USD, USD/JPY) |
| AI Engine | Claude API (Anthropic Sonnet) |
| Trading Mode | Paper trading + Live ($100–$500 initial capital) |
| Target User (Phase 0) | Founder (Abenezer) — sole user and tester |
| Target User (Phase 1+) | Aspiring active traders, 25–45, $500–$50K capital |
| Pricing Model (future) | SaaS subscriptions ($29–$199/month) |
| Infrastructure | Cloud-primary + local backup redundancy |
| Development Approach | Claude Code (VS Code) — AI-assisted development |


| Goal | Description | Metric | Target |
|---|---|---|---|
| System reliability | Bot runs 24/7 without manual intervention | Uptime % | > 99% |
| Trading performance | Positive expectancy over 50+ paper trades | Win rate | > 45% |
| Risk discipline | No single session loss exceeds limit | Max daily drawdown | < 5% |
| AI quality | Signals are logical and explainable | Validation pass rate | > 95% |
| Execution accuracy | Orders placed match intended parameters | Fill accuracy | > 99% |
| Crash recovery | System recovers without human help | Recovery time | < 60s |
| Data integrity | No trades on stale or corrupt data | Data gaps caught | 100% |
| Alert delivery | All critical events reach operator | Alert delivery rate | > 99% |


| Metric | Definition | Target |
|---|---|---|
| Monthly Recurring Revenue | Paid subscriptions × avg price | $5,900 MRR (breakeven) |
| Paying Users | Active subscribers with live broker connected | 100 users |
| Churn Rate | Users cancelling per month | < 5% |
| Net Promoter Score | User satisfaction score | > 50 |
| System Uptime | Platform availability SLA | 99.9% |
| Support Ticket Volume | Issues requiring human intervention | < 2% of users/month |
| API Error Rate | Broker API call failures | < 0.1% |
| Time to First Trade | New user onboarding to first paper trade | < 10 minutes |


| Attribute | Detail |
|---|---|
| Name | Abenezer (Founder) |
| Role | Sole operator, tester, and product owner |
| Technical level | Non-developer; uses Claude Code in VS Code |
| Trading experience | Learning forex; building knowledge through system use |
| Capital | $100–$500 initial live capital; paper trading first |
| Goals | Validate strategy, generate passive income, build SaaS product |
| Pain points | Cannot monitor markets 24/7; needs reliable automation |
| Monitoring preference | Web dashboard + SMS alerts + daily email report |
| AI transparency need | Full — summary + expandable detailed reasoning per trade |


| Attribute | Detail |
|---|---|
| Demographics | 28–42 years old, employed full-time, $60K–$130K income |
| Trading capital | $1,000–$25,000 available for trading |
| Experience | Tried Robinhood/Coinbase; some forex knowledge; frustrated by manual trading |
| Key pain point | Cannot watch markets during workday; emotional decision-making |
| Desired outcome | Consistent passive income from automated, disciplined trading |
| Willingness to pay | $49–$99/month for a system that proves positive returns |
| Technology comfort | Comfortable with web apps; not a developer |
| Trust requirements | Needs to see trade reasoning, not just results |


| Attribute | Detail |
|---|---|
| Demographics | 25–38, technical background, may be developer or quant-adjacent |
| Trading capital | $500–$10,000 |
| Experience | Built or tried trading bots; dissatisfied with MT4/MT5 limitations |
| Key pain point | Wants AI-augmented signal generation without building from scratch |
| Desired outcome | A robust platform to test and deploy custom rules with AI overlay |
| Willingness to pay | $79–$199/month for advanced features and API access |
| Technology comfort | High — wants API access, advanced analytics, raw signal data |
| Trust requirements | Wants full indicator data, confidence scores, and trade logs |


| User Story | Acceptance Criteria |
|---|---|
| As a user, I want to connect my OANDA practice account so the system can paper trade on my behalf. | OANDA API key stored encrypted; connection tested; account balance displayed on dashboard within 30 seconds of setup. |
| As a user, I want to switch between paper trading and live trading mode so I can test safely before risking capital. | Mode toggle available in settings; switching requires confirmation dialog; all trade logs clearly labeled with mode. |
| As a user, I want the system to validate my OANDA connection on startup so I know it is working before markets open. | Health check runs on boot; passes if API responds within 5s; SMS alert sent if connection fails. |


| User Story | Acceptance Criteria |
|---|---|
| As a user, I want the AI to analyze forex markets every 15 minutes so I receive timely trading signals. | Signal scan runs on a configurable interval (default 15 min); each scan logs timestamp, pair, and outcome to database. |
| As a user, I want each AI signal to include a plain-English summary so I understand why a trade was or was not taken. | Every signal record contains a summary field of 2–4 sentences in plain English. |
| As a user, I want to expand any signal to see full technical detail so I can learn from every decision. | Dashboard expandable panel shows: RSI, MACD, EMA values, timeframe confluence scores, news context, confidence breakdown, and AI raw reasoning. |
| As a user, I want signals below a confidence threshold of 0.65 to be automatically rejected so the system does not overtrade. | Signals below threshold are logged as HOLD with reason; no order placed; threshold configurable in settings. |


| User Story | Acceptance Criteria |
|---|---|
| As a user, I want the system to never risk more than 2% of my account on a single trade so my capital is protected. | Position size calculated from account balance × risk % / (SL pips × pip value); max 2% enforced; configurable 0.5–2%. |
| As a user, I want trading to automatically pause if I lose 5% of my account in one day so I avoid catastrophic drawdown. | Daily P&L tracked in real-time; when −5% threshold hit, all new signals blocked; SMS alert sent; resumes next trading session. |
| As a user, I want the system to skip trades during high-impact news events so I avoid unpredictable volatility. | Economic calendar checked before each signal; trades blocked 30 min before and 15 min after red-folder events. |
| As a user, I want a maximum of 3 concurrent open positions so I am never overexposed. | Open position count checked before execution; 4th trade rejected with reason logged. |


| User Story | Acceptance Criteria |
|---|---|
| As a user, I want orders placed by the system to always include a stop loss and take profit so no trade is unmanaged. | Every market order submitted with attached SL and TP; order rejected internally if either is missing. |
| As a user, I want the system to confirm every fill so I know the order was actually executed at the intended price. | Post-fill verification runs within 2s; checks fill price vs intended; logs slippage; alerts if slippage > 3 pips. |
| As a user, I want failed orders to be logged with the exact error reason so I can diagnose issues. | All OANDA API error codes mapped to human-readable reasons; logged to risk_events table with full context. |


| User Story | Acceptance Criteria |
|---|---|
| As a user, I want a real-time dashboard showing my account balance, open positions, and today's P&L. | Dashboard updates within 5 seconds of any change; shows balance, equity, open trades, daily P&L, win/loss count. |
| As a user, I want to receive an SMS alert for every trade opened or closed so I am always informed. | SMS sent via Twilio within 30s of trade open/close; message includes pair, direction, size, price, and P&L (on close). |
| As a user, I want a daily performance email at 6pm EST so I can review the day's results. | Automated email via SendGrid at 18:00 EST; includes: trades taken, wins, losses, P&L, win rate, signals generated. |
| As a user, I want to see a historical trade log with filtering so I can analyze performance over time. | Trade history table with filters: date range, pair, outcome, direction; sortable columns; export to CSV. |


| User Story | Acceptance Criteria |
|---|---|
| As a user, I want the system to automatically restart after a crash so it does not require manual intervention overnight. | Supervisord restarts process within 30s; crash logged with full stack trace; SMS alert sent; open positions verified safe. |
| As a user, I want the local backup to activate if the cloud server goes down so trading never stops. | Local heartbeat monitor polls cloud health endpoint every 60s; activates after 3 missed beats; uses same Supabase DB. |
| As a user, I want a kill switch that immediately halts all trading and closes open positions in an emergency. | Kill switch accessible from dashboard and SMS command; closes all positions at market; disables signal scanning; logs event. |


| Requirement ID | Requirement | Priority |
|---|---|---|
| DE-001 | Connect to OANDA streaming API for real-time bid/ask price feed | Critical |
| DE-002 | Fetch OHLC candle data for M5, M15, H1, H4, and D timeframes | Critical |
| DE-003 | Compute RSI(14), MACD(12,26,9), EMA(20,50,200), ATR(14), Bollinger Bands(20,2) in real-time | Critical |
| DE-004 | Detect and flag stale price data (older than 5 seconds during market hours) | Critical |
| DE-005 | Detect and reject price spikes beyond 3 standard deviations from rolling mean | High |
| DE-006 | Validate OHLC integrity (Low <= Open <= High, Low <= Close <= High) on every candle | High |
| DE-007 | Detect and log candle gaps in historical data before indicator computation | High |
| DE-008 | Monitor bid-ask spread and flag when exceeding 3 pips (configurable threshold) | High |
| DE-009 | Integrate economic calendar API and store upcoming high-impact events | High |
| DE-010 | Automatically switch to REST polling fallback if streaming connection drops | High |
| DE-011 | Support currency pairs: EUR/USD, GBP/USD, USD/JPY (extensible architecture) | Critical |
| DE-012 | Log all raw data received and validation outcomes to database for audit | Medium |


| Requirement ID | Requirement | Priority |
|---|---|---|
| AI-001 | Generate trading signals every 15 minutes per configured pair using Claude API | Critical |
| AI-002 | Implement multi-timeframe confluence: H4 trend + H1 structure + M15 entry alignment | Critical |
| AI-003 | Return structured JSON output with action, confidence, entry, SL, TP, reasoning, summary | Critical |
| AI-004 | Validate all AI output fields against schema before any downstream processing | Critical |
| AI-005 | Cross-validate AI confidence score against computed indicator alignment score | Critical |
| AI-006 | Adjust confidence score downward for news proximity, low-liquidity sessions, wide spreads | High |
| AI-007 | Provide plain-English trade summary (2–4 sentences) for every signal | Critical |
| AI-008 | Provide expandable detailed breakdown: per-indicator values, confluence scores, reasoning chain | Critical |
| AI-009 | Implement retry protocol: up to 3 AI attempts before falling back to rule-based signal | High |
| AI-010 | Log every AI prompt sent and response received for audit and future training | High |
| AI-011 | Reject signals with confidence below configurable threshold (default 0.65) | Critical |
| AI-012 | Enforce risk/reward minimum ratio of 1.5:1 on all signals regardless of AI confidence | Critical |
| AI-013 | Block all signals during configured news blackout windows | Critical |
| AI-014 | Support session-aware trading: prioritize London/NY overlap hours (13:00–17:00 EST) | High |


| Requirement ID | Requirement | Priority |
|---|---|---|
| RE-001 | Calculate position size dynamically: (Account Balance × Risk%) / (SL pips × Pip Value) | Critical |
| RE-002 | Enforce maximum risk per trade of 2% of account balance (configurable 0.5–2%) | Critical |
| RE-003 | Track daily P&L in real-time and halt trading when daily loss limit reached (default 5%) | Critical |
| RE-004 | Track weekly P&L and halt trading when weekly loss limit reached (default 10%) | Critical |
| RE-005 | Enforce maximum concurrent open positions (default 3, configurable 1–5) | Critical |
| RE-006 | Filter out signals when spread exceeds maximum threshold (default 3 pips) | High |
| RE-007 | Block trades 30 minutes before and 15 minutes after high-impact news events | High |
| RE-008 | Enforce minimum risk/reward ratio of 1.5:1 on all trades | Critical |
| RE-009 | Log all risk rejections with reason code and timestamp to risk_events table | High |
| RE-010 | Raise confidence threshold automatically after 3 consecutive losses (circuit breaker) | High |
| RE-011 | Prevent duplicate signal execution for same pair within cooldown period (default 60 min) | High |
| RE-012 | Provide emergency kill switch that halts trading and can close all positions | Critical |


| Requirement ID | Requirement | Priority |
|---|---|---|
| EX-001 | Place market orders via OANDA v20 REST API with attached SL and TP | Critical |
| EX-002 | Implement order state machine: PENDING → SUBMITTED → ACKNOWLEDGED → FILLED → MANAGED → CLOSED | Critical |
| EX-003 | Verify every fill within 2 seconds: confirm fill price, units, SL, TP on OANDA | Critical |
| EX-004 | Calculate and log slippage in pips for every fill; alert if slippage exceeds 3 pips | High |
| EX-005 | Handle partial fills: recalculate SL/TP based on actual fill size | High |
| EX-006 | Implement exponential backoff retry for transient API failures (max 3 retries) | High |
| EX-007 | Implement circuit breaker: trip after 3 failures in 60s; half-open after 30s | Critical |
| EX-008 | Query order status before retrying to prevent duplicate orders | Critical |
| EX-009 | Support order modification: update SL/TP on open positions | High |
| EX-010 | Support position close: close all or individual positions via API | Critical |
| EX-011 | Log every API call, response code, and latency to execution log table | High |
| EX-012 | Support both paper trading mode (simulated) and live trading mode (real API) | Critical |


| Requirement ID | Requirement | Priority |
|---|---|---|
| DB-001 | Display real-time account balance, equity, margin used, and margin available | Critical |
| DB-002 | Display all open positions with pair, direction, size, entry price, current P&L, SL, TP | Critical |
| DB-003 | Display today's performance: trades taken, win/loss, pips, dollar P&L, win rate | Critical |
| DB-004 | Display system status indicators for: AI Brain, Data Feed, OANDA API, Risk Engine, Circuit Breaker | Critical |
| DB-005 | Display recent signals feed showing pair, direction, confidence, action taken, timestamp | High |
| DB-006 | Expandable signal detail panel showing full AI reasoning, indicators, confluence breakdown | Critical |
| DB-007 | Display trade history table with filters (date, pair, outcome, direction) and CSV export | High |
| DB-008 | Display equity curve chart for configurable time range (1D, 1W, 1M, all) | High |
| DB-009 | Display performance analytics: win rate, profit factor, avg win/loss, max drawdown, Sharpe | High |
| DB-010 | Display recent system alerts and risk events log | High |
| DB-011 | Provide kill switch control accessible from dashboard | Critical |
| DB-012 | Settings panel: configure risk %, daily limit, max positions, confidence threshold, trading pairs | High |
| DB-013 | Real-time updates via WebSocket or Supabase Realtime (no page refresh required) | High |
| DB-014 | Responsive design supporting desktop web browsers (mobile web usable, native app later) | Medium |


| Requirement | Target | Measurement Method |
|---|---|---|
| Price feed latency | < 500ms from market tick to system receipt | OANDA streaming timestamp vs system receipt |
| Signal generation time | < 10 seconds end-to-end (data → AI → validation → decision) | Logged timestamps per stage |
| Order placement latency | < 2 seconds from decision to OANDA API call | Execution log timestamps |
| Dashboard load time | < 2 seconds initial load | Lighthouse performance audit |
| Dashboard data refresh | < 5 seconds for real-time data updates | WebSocket event timing |
| Database query time | < 200ms for all dashboard queries | Supabase query logs |
| Crash recovery time | < 60 seconds from crash to resumed operation | Supervisord restart logs |
| Failover activation time | < 180 seconds from primary failure to local takeover | Heartbeat monitor logs |


| Requirement | Target | Notes |
|---|---|---|
| System uptime | > 99% during forex market hours (Sun 17:00 – Fri 17:00 EST) | Excluding planned maintenance |
| Crash recovery | Auto-restart within 60 seconds for any unhandled exception | Supervisord with 5 retry limit |
| Data integrity | 100% of data validation checks must execute before any signal is generated | No bypasses allowed |
| Order safety | Zero duplicate orders — idempotency enforced on all order submissions | State machine + query-before-retry |
| Position reconciliation | System state reconciled against OANDA on every startup and crash recovery | Mandatory reconciliation protocol |
| Alert delivery | > 99% of critical alerts delivered within 60 seconds | Twilio delivery receipts |
| Backup activation | Local backup activates automatically — no human intervention required | Distributed lock protocol |


| Requirement | Standard | Implementation |
|---|---|---|
| API key storage | Never in code or database — secrets manager only | Railway env vars → HashiCorp Vault (V2) |
| Key isolation | Read-only key for data; trading key only for execution module | Two separate OANDA API keys |
| IP whitelisting | OANDA API keys locked to cloud server IP only | OANDA account settings |
| Transport security | TLS 1.3 only for all external API communications | HTTPX with TLS enforcement |
| Log scrubbing | All log output scrubbed for tokens, keys, and sensitive patterns | SecureLogger middleware |
| Dependency locking | All package versions pinned; hash verification enabled | requirements.txt with hashes |
| Key rotation | All API keys rotated every 90 days | Documented rotation procedure |
| Database encryption | All data encrypted at rest; no plaintext credentials stored | Supabase encryption at rest |


| Attribute | Specification |
|---|---|
| Feature ID | FEAT-001 |
| Priority | Critical — Core differentiator |
| Description | AI analyzes three timeframes simultaneously (H4, H1, M15) and only generates actionable signals when all three confirm the same directional bias. |
| Scan interval | Every 15 minutes per configured currency pair (configurable 5–60 min) |
| Timeframe roles | H4: trend direction via EMA 50/200 crossover. H1: key support/resistance levels and structure. M15: entry trigger via RSI reversal + MACD crossover. |
| Confluence scoring | Each timeframe contributes a score (0–1). All three must score > 0.6 for signal generation. Weighted: H4 = 0.40, H1 = 0.35, M15 = 0.25. |
| AI prompt structure | Structured prompt includes: current price, last 50 candles per timeframe, all indicator values, session, spread, news events, recent trade history. Returns validated JSON. |
| Output fields | action (BUY/SELL/HOLD), confidence (0–1), entry_price, stop_loss, take_profit, reasoning (full text), summary (2–4 sentences), indicators_used (JSON), timeframe_scores (JSON). |
| Fallback behavior | If Claude API fails after 3 retries, system falls back to rule-based signal generation using indicator thresholds only. Result labeled as RULE_BASED. |
| Session filter | Signals only generated during London session (08:00–17:00 GMT) and NY session (13:00–22:00 GMT). Configurable. |


| Attribute | Specification |
|---|---|
| Feature ID | FEAT-002 |
| Priority | Critical — Capital protection |
| Position sizing formula | Units = (Balance × Risk%) / (SL_pips × Pip_Value_per_unit) |
| Dynamic confidence scaling | Confidence 0.65–0.79 → 0.5% risk. Confidence 0.80–0.89 → 1.0% risk. Confidence 0.90+ → 2.0% risk. |
| Daily loss halt | When daily P&L reaches −5% of opening balance, all new signals blocked for remainder of session. Auto-resets at 17:00 EST. |
| Weekly loss halt | When weekly P&L reaches −10% of Monday opening balance, system halts entirely. Requires manual restart with confirmed acknowledgment. |
| Consecutive loss escalation | After 3 consecutive losses, minimum confidence threshold raised from 0.65 to 0.75. After 5 consecutive losses, raised to 0.85. |
| News blackout | 30 minutes before any High-impact (red) economic event on configured pairs. 15 minutes after event concludes. Medium-impact events: 15 minutes before only. |
| Spread filter | Signal rejected if spread > 3.0 pips for majors, > 4.0 pips for minors. Values configurable. |
| Max positions | Configurable 1–5. Default 3. New signal rejected if at or above limit. |
| Cooldown period | No new signal for same pair for 60 minutes after a trade is opened. Prevents overtrading single pair. |


| Attribute | Specification |
|---|---|
| Feature ID | FEAT-003 |
| Priority | Critical — Differentiating feature |
| Signal card components | Pair icon + name. Direction badge (BUY/SELL/HOLD). Confidence percentage bar. Action taken (EXECUTED/REJECTED + reason). Timestamp. Plain-English summary (always visible). |
| Expandable detail panel | Activated by clicking signal card. Shows: Full AI reasoning text. Per-indicator table (RSI, MACD, EMA values with signals). Timeframe confluence scores (H4/H1/M15 bars). Confidence adjustment breakdown. News events active at time. Risk parameters used. |
| Signal history | Searchable, filterable log of all signals generated. Filters: pair, date range, action, confidence range, session. Default: last 50 signals. |
| Live signal feed | Real-time feed updates when new signal is generated. Visual notification badge. Feed auto-scrolls to newest. |
| Performance attribution | Each closed trade links back to its originating signal. Win/loss tagged on signal card after trade closes. |


| Attribute | Specification |
|---|---|
| Feature ID | FEAT-004 |
| Priority | Critical — Pre-live validation |
| Description | Full simulation of live trading using real market prices from OANDA but no real capital at risk. Identical code path as live trading — only the order submission step differs. |
| Paper account | Virtual balance configurable (default $10,000). Resets available at any time. |
| Simulation fidelity | Uses actual OANDA bid/ask prices at time of signal. Simulates realistic spread costs. Does not simulate slippage (simplified). |
| Mode isolation | Paper and live trades are stored separately. Dashboard clearly labels all paper trades. No paper trade ever touches OANDA live trading API. |
| Switching | Mode switch requires: confirmation dialog. Minimum 50 paper trades logged before live mode unlocks (soft gate — can be bypassed by owner). |
| Paper P&L tracking | Full P&L tracking in paper mode identical to live mode. Performance analytics computed identically. |


| Attribute | Specification |
|---|---|
| Feature ID | FEAT-005 |
| Priority | Critical |
| Trade log fields | Trade ID, timestamp open/close, pair, direction, entry/exit price, SL, TP, position size, P&L pips, P&L USD, duration, outcome, confidence score, session, AI summary, exit reason. |
| Performance metrics computed | Win rate %, profit factor, average win (pips + USD), average loss (pips + USD), largest win, largest loss, max drawdown, Sharpe ratio (annualized), consecutive wins/losses, expectancy per trade. |
| Equity curve | Line chart showing cumulative account equity over time. Configurable range: 1D, 1W, 1M, 3M, All. Drawdown overlay toggleable. |
| Pair breakdown | Performance metrics segmented by currency pair. Identify which pairs are most/least profitable. |
| Session breakdown | Performance metrics segmented by trading session (London, NY, overlap, other). |
| Export | Full trade log exportable to CSV for external analysis. |
| Data retention | All trade records retained indefinitely. System state snapshots retained for 30 days. |


| Feature | Description | Business Value |
|---|---|---|
| Multi-broker support | Add Alpaca (stocks), CCXT (crypto), expanding beyond OANDA | Addresses all target markets |
| Backtesting engine | Run AI strategy against 12+ months of historical data; generate performance report | Strategy validation before live capital |
| Strategy customization | User-configurable indicator weights, session filters, confidence thresholds via UI | Reduces churn for power users |
| Trailing stop management | AI dynamically adjusts stop loss as trade moves in favor | Improves profit capture |
| News sentiment layer | Real-time financial news NLP feeding into AI confidence adjustment | More context-aware signals |
| Mobile web optimization | Full responsive design for mobile browser; PWA support | On-the-go monitoring |
| Multi-user architecture | Tenant isolation, per-user broker credentials, user management | SaaS commercialization |
| Stripe billing integration | Subscription tiers, payment processing, trial periods | Revenue generation |


| Feature | Description | Business Value |
|---|---|---|
| Social/copy trading | Follow top-performing strategy profiles; auto-mirror their signals | Network effects, user acquisition |
| Strategy marketplace | Users publish and monetize their strategies; platform takes % fee | New revenue stream |
| Native mobile app | iOS and Android apps with push notifications, biometric auth | Higher engagement and retention |
| Options & derivatives | Options chain analysis, covered calls, protective puts via AI | Premium tier differentiation |
| White-label API | Financial advisors and fintechs embed Lumitrade engine via API | B2B revenue stream |
| ML model training | Train custom models on accumulated trade outcome data | Competitive moat deepens over time |
| Advanced portfolio analytics | Correlation analysis, beta, portfolio-level risk metrics | Institutional-grade reporting |
| Regulatory compliance tools | Trade reporting, tax lot tracking, compliance documentation | Enterprise and RIA market entry |


| Field | Type / Constraints |
|---|---|
| action | string — enum: BUY / SELL / HOLD |
| confidence | float — range: 0.0 to 1.0 inclusive |
| entry_price | float — must be within 0.5% of current live price |
| stop_loss | float — BUY: must be < entry_price. SELL: must be > entry_price |
| take_profit | float — BUY: must be > entry_price. SELL: must be < entry_price. Min RR 1.5:1 |
| summary | string — 2 to 4 sentences. Plain English. No jargon. Suitable for non-expert reader. |
| reasoning | string — Full technical analysis. Min 100 words. Include specific indicator values cited. |
| timeframe_h4_score | float — 0.0 to 1.0. Confidence from H4 timeframe analysis alone. |
| timeframe_h1_score | float — 0.0 to 1.0. Confidence from H1 timeframe analysis alone. |
| timeframe_m15_score | float — 0.0 to 1.0. Confidence from M15 timeframe analysis alone. |
| key_levels | array of floats — up to 3 support/resistance levels identified |
| invalidation_level | float — price level at which the trade thesis is invalidated |
| expected_duration | string — estimated trade duration: SCALP (<1hr), INTRADAY (1–8hr), SWING (1–3 days) |


| Factor | Adjustment Rule | Max Impact |
|---|---|---|
| Indicator alignment | Score = % of indicators confirming AI direction. Multiply confidence by (0.5 + alignment_score × 0.5) | −50% if all indicators disagree |
| News proximity | High-impact event < 60 min: −0.15. High-impact event < 30 min: −0.25 | −0.25 |
| Session quality | London/NY overlap (13:00–17:00 EST): +0.05. Thin session (Tokyo only): −0.10 | +0.05 / −0.10 |
| Spread penalty | Spread > 2 pips: −0.05. Spread > 3 pips: signal rejected entirely | −0.05 or reject |
| Consecutive losses | 3 losses: effective threshold raised to 0.75. 5 losses: threshold raised to 0.85 | Threshold shift |
| Recent pair performance | Last 5 trades on pair < 40% win rate: −0.10 to confidence | −0.10 |


| Variable | Source / Formula |
|---|---|
| Account Balance | Live from OANDA API at time of signal execution |
| Risk Percentage | User-configured. Default: scaled by confidence (0.5% / 1.0% / 2.0%) |
| Risk Amount (USD) | Account Balance × Risk Percentage |
| Stop Loss (pips) | abs(entry_price − stop_loss) / pip_size(pair) |
| Pip Value (USD/unit) | For EUR/USD: $0.0001/unit. For USD/JPY: $0.01/unit. Calculated per pair. |
| Position Size (units) | Risk Amount / (SL_pips × Pip_Value_per_unit) |
| Rounded to | Nearest 1,000 units (micro lot = 1,000 units on OANDA) |
| Minimum size | 1,000 units (enforced — no smaller positions) |
| Maximum size | Capped at 2% risk regardless of confidence score |


| State | Condition to Enter | Behavior |
|---|---|---|
| NORMAL | Default state on startup | All signals processed normally through full pipeline |
| CAUTIOUS | 3 consecutive losses OR daily P&L < −2.5% | Confidence threshold raised to 0.75. Max risk per trade reduced to 0.5%. |
| NEWS_BLOCK | High-impact event within configured window | All new signals blocked. Open positions continue to be managed. |
| DAILY_LIMIT | Daily P&L reaches −5% of opening balance | All new signals blocked for remainder of session. Resets at 17:00 EST. |
| WEEKLY_LIMIT | Weekly P&L reaches −10% | Full halt. No signals processed. Manual restart required with acknowledgment. |
| CIRCUIT_OPEN | Broker API: 3 failures in 60 seconds | No new orders placed. Existing positions monitored via read-only API. Resets after 30s test. |
| EMERGENCY_HALT | Kill switch activated by user | All signals blocked. All open positions closed at market. Requires manual restart. |


| Column | Type | Description |
|---|---|---|
| id | UUID PK | Internal account identifier |
| owner_name | TEXT | Account owner name |
| broker | TEXT | Broker name: OANDA |
| broker_account_id | TEXT | OANDA account ID (not API key) |
| account_type | TEXT ENUM | PRACTICE or LIVE |
| base_currency | TEXT | Account base currency (USD) |
| created_at | TIMESTAMPTZ | Account creation timestamp |
| is_active | BOOLEAN | Whether account is currently active |


| Column | Type | Description |
|---|---|---|
| id | UUID PK | Internal trade identifier |
| account_id | UUID FK | References accounts.id |
| signal_id | UUID FK | References signals.id that triggered this trade |
| broker_trade_id | TEXT | OANDA trade ID for reconciliation |
| pair | TEXT | Currency pair: EUR_USD, GBP_USD, USD_JPY |
| direction | TEXT ENUM | BUY or SELL |
| mode | TEXT ENUM | PAPER or LIVE |
| entry_price | DECIMAL(10,5) | Actual fill price |
| exit_price | DECIMAL(10,5) | Actual exit price (null if open) |
| stop_loss | DECIMAL(10,5) | Stop loss price at entry |
| take_profit | DECIMAL(10,5) | Take profit price at entry |
| position_size | INTEGER | Size in units |
| confidence_score | DECIMAL(4,3) | Adjusted confidence at time of execution |
| slippage_pips | DECIMAL(5,1) | Slippage from intended vs actual fill |
| pnl_pips | DECIMAL(7,1) | P&L in pips (null if open) |
| pnl_usd | DECIMAL(10,2) | P&L in USD (null if open) |
| status | TEXT ENUM | OPEN, CLOSED, CANCELLED |
| exit_reason | TEXT ENUM | SL_HIT, TP_HIT, AI_CLOSE, MANUAL, EMERGENCY |
| outcome | TEXT ENUM | WIN, LOSS, BREAKEVEN (null if open) |
| session | TEXT ENUM | LONDON, NEW_YORK, OVERLAP, TOKYO, OTHER |
| opened_at | TIMESTAMPTZ | Trade open timestamp |
| closed_at | TIMESTAMPTZ | Trade close timestamp (null if open) |
| duration_minutes | INTEGER | Trade duration in minutes (null if open) |


| Column | Type | Description |
|---|---|---|
| id | UUID PK | Signal identifier |
| account_id | UUID FK | References accounts.id |
| pair | TEXT | Currency pair analyzed |
| timeframe_primary | TEXT | Primary timeframe: M15 |
| action | TEXT ENUM | BUY, SELL, HOLD |
| confidence_raw | DECIMAL(4,3) | Raw confidence from AI before adjustment |
| confidence_adjusted | DECIMAL(4,3) | Final confidence after adjustment pipeline |
| confidence_adjustment_log | JSONB | Breakdown of each adjustment factor and value |
| entry_price | DECIMAL(10,5) | AI-suggested entry price |
| stop_loss | DECIMAL(10,5) | AI-suggested stop loss |
| take_profit | DECIMAL(10,5) | AI-suggested take profit |
| summary | TEXT | Plain-English summary for dashboard display |
| reasoning | TEXT | Full AI technical reasoning text |
| indicators_snapshot | JSONB | All indicator values at time of signal |
| timeframe_scores | JSONB | H4, H1, M15 individual confluence scores |
| key_levels | JSONB | Support/resistance levels identified |
| news_context | JSONB | Economic events active or upcoming at signal time |
| session | TEXT ENUM | Trading session at time of signal |
| spread_pips | DECIMAL(5,1) | Spread at time of signal generation |
| executed | BOOLEAN | Whether signal resulted in a trade |
| rejection_reason | TEXT | Why signal was not executed (if applicable) |
| generation_method | TEXT ENUM | AI or RULE_BASED (fallback) |
| ai_prompt_hash | TEXT | SHA256 of prompt sent to AI for audit |
| created_at | TIMESTAMPTZ | Signal generation timestamp |


| Table | Purpose |
|---|---|
| risk_events | All risk engine decisions: rejections, limit hits, circuit breaker trips, news blocks. Includes type, reason, severity, and context. |
| system_state | Single-row persistent state: current risk state, open positions count, daily P&L, circuit breaker status, last signal timestamps per pair. Updated every 30 seconds. |
| performance_snapshots | Daily performance summary: balance, trades, wins, losses, P&L, win rate, profit factor, max drawdown. One row per day. |
| execution_log | Every OANDA API call: endpoint, method, request params, response code, latency, error if any. Full audit trail. |
| ai_interaction_log | Every Claude API call: prompt (hashed), response, validation result, retry count, latency. Audit and training data. |
| alerts_log | Every alert sent: channel (SMS/email), recipient, message, delivery status, timestamp. |
| system_events | System lifecycle events: startup, shutdown, crash, recovery, mode switch, kill switch activation. |


| Threat | Risk Level | Primary Mitigation |
|---|---|---|
| API key exposure via source code or GitHub commit | Critical | Secrets manager only. Pre-commit hooks. .gitignore. No keys in code ever. |
| API key exposure via logs or error messages | Critical | SecureLogger middleware scrubs all output. Pattern-matching on tokens. |
| Compromised cloud server — all keys stolen | Critical | IP whitelisting on OANDA. Separate read-only and trading keys. Key rotation every 90 days. |
| Unauthorized trading — attacker places orders | Critical | OANDA IP whitelist locks API to cloud server IP only. Rate limiting on execution engine. |
| Man-in-the-middle — trade data intercepted | High | TLS 1.3 enforced on all connections. Certificate validation on all HTTPS requests. |
| Dependency supply chain attack | High | All dependencies pinned to exact versions with hash verification. Regular audit. |
| Database breach — trade history exposed | Medium | Supabase encryption at rest. Row-level security. No plaintext secrets in any table. |
| Runaway bot — bug causes excessive trading | High | Daily and weekly loss limits. Max position limits. Circuit breaker. Human kill switch. |
| Prompt injection via market data | Medium | Market data is structured numeric input — never interpolated as natural language instructions. |


| Regulatory Area | Current Position & Future Action |
|---|---|
| Investment Advisor status | Phase 0: Not applicable (personal use only). Phase 1: Position as automation tool, not advisory service. Consult FinTech attorney before launch. |
| Forex regulations (CFTC) | OANDA is a registered FCM/RFED. Users trade their own accounts. Lumitrade is automation software, not a counterparty. |
| Copy trading rules | Not applicable Phase 0. V3 social trading feature requires legal review. Structure as signal mirroring, not managed accounts. |
| Data privacy (CCPA/GDPR) | Phase 0: Single user, not applicable. Phase 1+: Privacy policy, data retention policy, user data deletion capability required before launch. |
| Terms of Service | Phase 1 requirement: Risk disclosure, limitation of liability, no investment advice warranty. FinTech attorney review required. |


| Layer | Technology | Version / Tier | Rationale |
|---|---|---|---|
| Backend runtime | Python | 3.11+ | Dominant language for finance/data. Best ecosystem for trading libraries. |
| Async framework | asyncio + aiohttp | stdlib | Native async for concurrent data streams without thread overhead. |
| AI engine | Anthropic Claude API | Sonnet (claude-sonnet-4-20250514) | Superior reasoning for structured JSON output and financial analysis. |
| Broker API | OANDA v20 REST + Streaming | v20 | Best retail forex API. Paper trading built-in. Fractional lots. Reliable. |
| Technical indicators | pandas-ta | Latest | 130+ indicators. Built on pandas. No reinventing the wheel. |
| Data manipulation | pandas + numpy | Latest | Industry standard for financial time series data. |
| Database | Supabase (PostgreSQL) | Free tier → Pro | Managed PostgreSQL with Realtime, Auth, and Storage. Scales to SaaS. |
| Dashboard frontend | Next.js + Tailwind CSS | 14 + 3.4 | SSR + Realtime support. Supabase client library native support. |
| Process supervisor | Supervisord | Latest | Auto-restart, log rotation, process management on Linux. |
| Cloud hosting (primary) | Railway.app | Hobby → Pro | $5/month. Persistent processes. Easy env var management. |
| Local backup | Local machine / Raspberry Pi | N/A | Heartbeat monitor. Activates on cloud failure via distributed lock. |
| Alerting — SMS | Twilio | Pay-as-you-go | Reliable programmatic SMS. ~$0.0075/message. |
| Alerting — Email | SendGrid | Free tier (100/day) | Transactional email. Daily performance reports. |
| Economic calendar | ForexFactory (scraped) / Tradingeconomics API | Free / Paid | High-impact news event data. Scraping as free tier; paid API for reliability. |
| Error tracking | Sentry | Free tier | Crash reports with full stack trace and context. Auto-alerts. |
| Uptime monitoring | UptimeRobot | Free tier | Pings /health endpoint every 60 seconds. SMS on downtime. |
| HTTP client | HTTPX | Latest | Async-native. TLS 1.3 support. Connection pooling. |
| Secrets (Phase 0) | Railway env vars | N/A | Simple, secure, Git-independent. |
| Secrets (Phase 1+) | HashiCorp Vault | Community | Enterprise-grade secrets management for multi-tenant. |
| CI/CD | GitHub Actions | Free tier | Auto-run test suite on every push before deploy. |


| Service | Estimated Monthly Cost |
|---|---|
| Railway.app (cloud hosting) | $5–10 |
| Supabase (database + realtime) | $0 (free tier for Phase 0) |
| Anthropic Claude API (signals) | $10–25 (varies with scan frequency) |
| Twilio SMS (alerts) | $2–5 |
| SendGrid (daily emails) | $0 (free tier) |
| OANDA API | $0 (free with account) |
| UptimeRobot | $0 (free tier) |
| Sentry | $0 (free tier) |
| ForexFactory / news data | $0–20 |
| Total Phase 0 estimated | $17–60/month |


| Endpoint | Method | Description |
|---|---|---|
| /health | GET | System health check. Returns status of all components. Used by UptimeRobot and local backup heartbeat. |
| /api/account/summary | GET | Account balance, equity, open position count, today's P&L. Refreshed every 30s. |
| /api/positions/open | GET | All open positions with live P&L calculation. |
| /api/signals/recent | GET | Last 50 signals with filters: pair, date range, action. Includes full detail for each. |
| /api/trades/history | GET | Paginated trade history with filters and sorting. CSV export endpoint included. |
| /api/performance/summary | GET | Computed performance metrics for configurable date range. |
| /api/performance/equity-curve | GET | Equity curve data points for chart rendering. |
| /api/system/alerts | GET | Recent system alerts and risk events. |
| /api/control/kill-switch | POST | Activates emergency halt. Requires confirmation token. |
| /api/settings | GET / PUT | Read and update system configuration (risk %, thresholds, pairs, limits). |


| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| AI generates consistently poor signals | Medium | High | Extensive paper trading before live capital. Backtesting requirement. Prompt iteration process. |
| OANDA API breaking change | Low | High | Version-pin API client. Monitor OANDA developer changelog. Abstract broker interface for swappability. |
| Claude API downtime or deprecation | Low | High | Rule-based fallback signal generation. Abstract AI interface. Monitor Anthropic status page. |
| Trading strategy stops working (regime change) | Medium | High | Regular performance review. Automatic threshold escalation. Human review triggers. |
| Capital loss beyond acceptable threshold | Low | High | Weekly loss limit halts system. Paper trading validation gate. Conservative initial position sizing. |
| Cloud server downtime | Low | Medium | Local backup with automatic failover. Distributed lock prevents dual trading. |
| Data feed corruption causes bad trade | Low | High | Multi-layer data validation pipeline. All data validated before AI receives it. |
| Regulatory change affecting automation | Low | Medium | Position as personal automation tool. Legal review before SaaS launch. |
| Scope creep delays Phase 0 delivery | High | Medium | Strict Phase 0 feature lock. Non-goals documented. Weekly review against roadmap. |


| Week | Focus Area | Key Deliverables | Reliability Gate |
|---|---|---|---|
| 1 | Environment & foundations | OANDA practice account + API key. Supabase project + schema. GitHub repo. Railway deployment. Environment variables. | API auth confirmed. DB connected. /health endpoint returns 200. |
| 2 | Data engine — feeds | OANDA streaming price feed. OHLC candle fetcher for all timeframes. Candle storage to DB. | Real-time prices flowing. Candles stored correctly for all 3 pairs. |
| 3 | Data engine — indicators + validation | All indicator computations. Price validation pipeline. Spike detection. Stale data detection. Gap detection. | All validation tests passing. Indicator values match TradingView reference. |
| 4 | AI brain — prompt + output | Claude API integration. Prompt assembly. JSON output parsing. Schema validation. Confidence adjustment pipeline. | 100% of validation unit tests green. Fallback rule-based signal working. |
| 5 | Risk engine | Position sizing formula. Risk state machine. All filtering rules. Daily/weekly limit tracking. News calendar integration. | All risk rules unit tested. Simulated stress tests pass. |
| 6 | Execution engine | Order state machine. OANDA order placement. Fill verification. Slippage logging. Circuit breaker. Paper trade simulation. | Paper trades placing and closing correctly. No duplicate orders in stress test. |
| 7 | State management + recovery | SystemState persistence. Crash recovery protocol. Position reconciliation. Failover distributed lock. Local heartbeat monitor. | Simulated crash test: system recovers and reconciles in < 60s. |
| 8 | Logging + alerting | Structured JSON logging. Supabase log tables. Twilio SMS alerts. SendGrid daily email. UptimeRobot configuration. | All log levels writing correctly. SMS alert delivered in test. Daily email delivered. |
| 9 | Dashboard — backend | All API endpoints built and tested. WebSocket or Supabase Realtime integration. Performance metric computation. | All endpoints return correct data. Latency < 200ms. Authenticated. |
| 10 | Dashboard — frontend | Next.js dashboard UI. Real-time account panel. Signal feed with expand detail. Trade history table. System status panel. | Dashboard loads in < 2s. Real-time updates working. All UI tests passing. |
| 11 | Kill switch + settings | Kill switch UI + API. Settings panel: all configurable parameters. Mode switch (paper/live). Configuration persistence. | Kill switch closes all positions in test. Settings save and apply correctly. |
| 12 | Paper trading run | System running 24/7 on Railway. Minimum 50 paper trades logged. Daily performance review. Prompt refinement. | 50+ paper trades logged. No system crashes. No unhandled errors in logs. |
| 13 | Security audit + go live | All API keys rotated. IP whitelist confirmed. Log scrubber verified. Go live with $100 real capital at 0.5% risk max. | Security checklist 100% complete. First live trade placed successfully. |


| Checkpoint | Required Standard | Verified By |
|---|---|---|
| Paper trade count | Minimum 50 completed trades | Trade history dashboard |
| Paper win rate | >= 40% win rate on 50+ sample | Performance analytics panel |
| System stability | 7 consecutive days without crash or manual intervention | System events log |
| Security audit | All items in Section 13 checklist complete | Manual review + gitleaks scan |
| Kill switch test | Tested and confirmed functional | Test log entry in system_events |
| Crash recovery test | Tested and confirmed < 60s recovery | Test log entry in system_events |
| Daily loss limit test | Confirmed halts trading at −5% | Test log entry in risk_events |
| Alert delivery test | SMS and email confirmed delivered | Test alert in alerts_log |
| Dashboard accuracy | All metrics match database — spot checked | Manual verification |
| Initial capital | Start with $100 maximum at 0.5% risk per trade | OANDA account setting |


| Attribute | Value |
|---|---|
| Version | 2.0 — includes future feature stubs and hooks |
| Phase 0 scope | Single user, OANDA forex, paper → live trading |
| Future features | 15 features documented as stubs — foundations built now |
| Trading mode | Paper first, live after 50+ trade gate |
| Next document | System Architecture Specification v2.0 |


| Attribute | Specification |
|---|---|
| What it does | Instead of one Claude making every decision, 3 AI models vote. Consensus required to trade. Disagreement = skip. |
| Phase to build | Phase 2 — after 200+ live trades prove single-model baseline |
| Why not Phase 0 | Need baseline performance data before adding complexity. Single model failure mode is safer to debug. |
| Voting logic | 2 of 3 agree → execute at standard size. All 3 agree → execute at +50% size. All 3 disagree → HOLD. |
| Models | Claude Sonnet (primary), Claude Opus (validation), GPT-4o (challenger). Configurable via settings. |
| Phase 0 foundation | ConsensusEngine stub class. Multi-model config fields in DB. OpenAI API key slot in .env.example. AI response schema extended with model_id field. |


| Attribute | Specification |
|---|---|
| What it does | Classifies current market as TRENDING / RANGING / HIGH_VOLATILITY / LOW_LIQUIDITY and adjusts strategy accordingly. |
| Phase to build | Phase 2 — immediately after Phase 0 proven. Biggest signal quality improvement available. |
| Regime logic | TRENDING: EMA spread > 0.2 ATR + price above/below all EMAs. RANGING: EMAs tangled + price oscillating. HIGH_VOL: ATR > 2x 30-day avg. LOW_LIQ: spread > 4 pips or outside market hours. |
| Strategy adjustments | TRENDING: wider stops (1.5x ATR), bigger targets (3:1 RR), standard sizing. RANGING: tighter stops (0.8x ATR), mean-reversion targets (1.5:1 RR), reduced sizing. HIGH_VOL: reduce to 0.5% risk or pause. LOW_LIQ: pause entirely. |
| Phase 0 foundation | MarketRegime enum in enums.py. regime: MarketRegime field on MarketSnapshot. RegimeClassifier stub in data_engine/. Regime displayed in dashboard status panel as a badge. |


| Attribute | Specification |
|---|---|
| What it does | Before each signal scan, a second AI call reads current financial news and produces a sentiment score per currency. |
| Phase to build | Phase 2 — after 200+ trades. Requires news API subscription. |
| Sentiment output | { "EUR": "BEARISH", "USD": "NEUTRAL", "GBP": "BULLISH", "confidence": 0.72, "key_headline": "ECB hinted at pause" } |
| Integration | Sentiment feeds into confidence adjustment pipeline. BEARISH sentiment on buy signal: -0.10 confidence. BULLISH on buy signal: +0.05. Conflicting: -0.15. |
| Phase 0 foundation | SentimentAnalyzer stub in ai_brain/. CurrencySentiment dataclass. sentiment_context field on MarketSnapshot (populated with neutral defaults). News sentiment section in prompt (empty until feature active). |


| Attribute | Specification |
|---|---|
| What it does | Prevents doubling exposure on correlated pairs. EUR/USD long + GBP/USD long = doubling USD short exposure. |
| Phase to build | Phase 2 — add to risk engine filters after core stable. |
| Correlation thresholds | > 0.80 correlation: reduce second position to 50%. > 0.90: reduce to 25% or skip. Correlation computed from 30-day rolling price returns. |
| Phase 0 foundation | CorrelationMatrix stub in risk_engine/. correlation_check in risk filters (returns approved, no reduction in Phase 0). correlation field in risk_events log for future analysis. |


| Attribute | Specification |
|---|---|
| What it does | Every Sunday evening, AI writes a plain-English trading journal covering the week's trades, what worked, what did not, and one specific recommendation. |
| Phase to build | Phase 2 — needs 50+ live trades before journals are meaningful. |
| Content | Best trade (why it worked), worst trade (why it failed), session performance breakdown, one actionable recommendation, win rate trend vs prior week. |
| Delivery | Email (SendGrid) + stored in trade_journals table. Viewable on /journal page in dashboard. |
| Phase 0 foundation | trade_journals table in DB schema. JournalGenerator stub in analytics/. Weekly scheduler hook in main.py (fires Sunday 20:00 EST, does nothing until enabled). /journal route stub in frontend. |


| Attribute | Specification |
|---|---|
| What it does | Users publish verified trading strategies. Other users subscribe. Creator earns 70% of subscription revenue. |
| Phase to build | Phase 3 — requires multi-user SaaS, Stripe Connect, performance verification. |
| Verification requirement | Strategy must have 90+ live trading days with auditable OANDA results. No backtested-only strategies. |
| Revenue split | Subscriber pays → Lumitrade receives → 70% to creator via Stripe Connect → 30% to Lumitrade. |
| Phase 0 foundation | strategies table and strategy_subscriptions table in DB. StrategyConfig dataclass (extends current signal scanner config). /marketplace route stub. Stripe Connect env var slot. |


| Attribute | Specification |
|---|---|
| What it does | Users follow verified traders. When the trader opens a position, copiers' accounts open proportional positions automatically. |
| Phase to build | Phase 3 — requires legal review, multi-user, signal mirroring infrastructure. |
| Legal positioning | Structured as "automated signal subscription" not "managed account" to avoid investment advisor registration in most jurisdictions. Requires FinTech attorney review before launch. |
| Performance fee | Copier pays 20% of profits generated from copied trades. Charged monthly. Via Stripe. |
| Phase 0 foundation | copy_relationships table. CopyTradeExecutor stub (mirrors signals to subscriber accounts). /copy route stub. Performance fee calculation stub. |


| Attribute | Specification |
|---|---|
| What it does | Conversational AI with access to your trade history. Explains any trade, answers questions about strategy, guides settings changes. |
| Phase to build | Phase 2 — after 100+ live trades provide enough context for meaningful coaching. |
| Access to | Full trade history, all AI signal reasoning, system settings, performance analytics. Read-only — cannot change settings directly. |
| Interface | Chat panel on /coach page. Persists conversation history per session. |
| Phase 0 foundation | coach_conversations table. CoachService stub in ai_brain/. /coach route stub in frontend. coach_context builder that assembles trade history summary for system prompt. |


| Attribute | Specification |
|---|---|
| What it does | Extends beyond OANDA forex to crypto (Coinbase), stocks (Alpaca), options (Tastytrade) using the same signal/risk/execution architecture. |
| Phase to build | Phase 3 — after SaaS proven with forex. Each asset class is a new broker connector. |
| Architecture readiness | Broker interface already abstracted. New asset = new BrokerClient implementation + asset-specific indicator parameters + market hours config. |
| Phase 0 foundation | BrokerInterface abstract base class (OANDA implements it). asset_class field on all trade/signal tables. Market-specific config structure in DB. Env var slots for Coinbase, Alpaca, Tastytrade API keys. |


| Attribute | Specification |
|---|---|
| What it does | iOS + Android app with push notifications, Face ID, home screen widgets, Apple Watch complication. |
| Phase to build | Phase 3 — web must be excellent first. App shares API layer with web dashboard. |
| Tech stack | React Native + Expo. Shares TypeScript types with Next.js frontend. Push via Expo Push or OneSignal. |
| Key features | Push notifications (replaces SMS for free), Face/Touch ID auth, P&L widget on home screen, Watch complication. |
| Phase 0 foundation | All API routes already REST + JSON (mobile-ready). Push notification token field on accounts table. /api/push/register route stub. EXPO_PUSH_TOKEN env var slot. |


| Attribute | Specification |
|---|---|
| What it does | Weekly AI-generated macro briefing: rate decisions, economic calendar preview, key levels, how Lumitrade's settings align with macro context. |
| Phase to build | Phase 2 — needs news aggregation API. Delivers immediate user value. |
| Delivery | Email Sunday evening + /intelligence page in dashboard. Stored in intelligence_reports table. |
| Phase 0 foundation | intelligence_reports table. IntelligenceReportGenerator stub. /intelligence route stub. Weekly scheduler slot (alongside journal scheduler). NEWS_API_KEY env var slot. |


| Attribute | Specification |
|---|---|
| What it does | Real-time probability of losing 25%, 50%, 100% of account based on current win rate, average win/loss, and risk per trade. |
| Formula | Risk of Ruin = ((1 - Edge) / (1 + Edge)) ^ (Capital / Unit_Risk) where Edge = (WR * AvgWin - LR * AvgLoss) / (WR * AvgWin + LR * AvgLoss) |
| Phase to build | Phase 2 — needs 20+ trades for meaningful calculation. Straightforward implementation. |
| Warnings | If ROR > 10%: WARNING badge in analytics. If ROR > 25%: ERROR badge + recommendation to reduce risk%. |
| Phase 0 foundation | RiskOfRuinCalculator stub in analytics/. risk_of_ruin field on performance_snapshots table. ROR panel stub in analytics page (shows "insufficient data" until 20+ trades). |


| Attribute | Specification |
|---|---|
| What it does | Visual environment to replay historical OANDA data through Lumitrade's signal engine and compare strategy parameter variations. |
| Phase to build | Phase 3 — substantial engineering effort (3-4 weeks). Highest-demand feature for power users. |
| Capability | Test any settings combination against 12–24 months of historical data. Side-by-side comparison of up to 3 configurations. Apply best config to live settings with one click. |
| Phase 0 foundation | BacktestRunner stub in analytics/. backtest_runs and backtest_results tables. /backtest route stub. Historical data fetcher method on OandaClient (already partially in candle_fetcher.py). |


| Attribute | Specification |
|---|---|
| What it does | REST API and WebSocket stream that lets developers and power users receive Lumitrade signals in external systems. |
| Phase to build | Phase 3 — after SaaS proven. Creates developer ecosystem. |
| Endpoints | GET /v1/signals/latest, WebSocket stream, GET /v1/analytics, POST /v1/webhooks (register endpoint for signal delivery). |
| Auth | API key per user. Rate limited. Generated in user settings. |
| Phase 0 foundation | api_keys table. ApiKeyMiddleware stub. /v1 route namespace in Next.js. Webhook delivery stub (fires on new signal but delivers to no endpoints until feature active). |


| Attribute | Specification |
|---|---|
| What it does | Pooled investment fund where Lumitrade AI trades on behalf of investors. Performance fee model: 1% management + 20% of profits. |
| Phase to build | Phase 4 — requires SEC/FINRA RIA registration (US) or equivalent. 3-5 year horizon. |
| Regulatory requirement | Investment Advisor registration mandatory before accepting external capital. Estimated legal cost: $15,000–50,000. Not a Phase 0–3 concern. |
| Revenue model | $10M AUM × 15% annual return × 20% performance fee = $300,000/year from one fund. Scales with AUM. |
| Phase 0 foundation | fund_accounts table stub. InvestorReporting stub. Compliance notes in SS document. Legal TODO documented. |


| Feature | Phase | Trigger | Phase 0 Cost |
|---|---|---|---|
| F-02 Market Regime Detection | 2 | Phase 0 proven | RegimeClassifier stub + enum |
| F-05 Trade Journal AI | 2 | 50+ live trades | journal table + stub + scheduler |
| F-08 AI Trading Coach | 2 | 100+ live trades | coach table + stub + route |
| F-12 Risk of Ruin Calculator | 2 | 20+ live trades | stub + DB field + UI panel |
| F-11 Intelligence Report | 2 | 200+ live trades | report table + stub + route |
| F-01 Multi-Model AI Brain | 2 | 200+ live trades | ConsensusEngine stub + config |
| F-03 News Sentiment AI | 2 | 200+ live trades | SentimentAnalyzer stub + prompt slot |
| F-04 Correlation Guard | 2 | Core stable | CorrelationMatrix stub + filter hook |
| F-09 Multi-Asset Expansion | 3 | SaaS proven | BrokerInterface abstract class |
| F-10 Native Mobile App | 3 | Web excellent | Push token field + API routes ready |
| F-06 Strategy Marketplace | 3 | 1000+ users | strategies table + Stripe env var |
| F-07 Copy Trading | 3 | 1000+ users | copy_relationships table + stub |
| F-13 Backtesting Studio | 3 | SaaS proven | BacktestRunner stub + tables |
| F-14 Public API + Webhooks | 3 | SaaS proven | api_keys table + /v1 namespace |
| F-15 Lumitrade Fund | 4 | Regulatory approval | fund table stub + legal TODO |
