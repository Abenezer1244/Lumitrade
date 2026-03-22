



LUMITRADE
DevOps Specification

ROLE 5 — SENIOR DEVOPS ENGINEER
Version 1.0  |  Railway + Docker + GitHub Actions + Supabase + UptimeRobot
Classification: Confidential
Date: March 20, 2026




# 1. Infrastructure Overview
## 1.1 Environment Map

## 1.2 Service Map

## 1.3 Cost Breakdown

# 2. Docker Configuration
## 2.1 backend/Dockerfile
Build Strategy  Multi-stage build. Stage 1 installs dependencies. Stage 2 copies only what is needed. Minimizes image size and attack surface.

# ── Stage 1: Dependency builder ───────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools for compiled packages
RUN apt-get update && apt-get install -y --no-install-recommends \
gcc g++ && \
rm -rf /var/lib/apt/lists/*

# Copy requirements and install to a dedicated prefix
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
--require-hashes -r requirements.txt

# ── Stage 2: Runtime image ─────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime only: supervisor for process management
RUN apt-get update && apt-get install -y --no-install-recommends \
supervisor curl && \
rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY lumitrade/ /app/lumitrade/
COPY supervisord.conf /etc/supervisor/conf.d/lumitrade.conf

# Create non-root user for security
RUN useradd --no-create-home --shell /bin/false lumitrade && \
mkdir -p /var/log/lumitrade && \
chown -R lumitrade:lumitrade /app /var/log/lumitrade

USER lumitrade

# Health check — Railway uses this for deploy gating
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/lumitrade.conf"]

## 2.2 backend/supervisord.conf
[supervisord]
nodaemon=true
user=lumitrade
logfile=/var/log/lumitrade/supervisord.log
logfile_maxbytes=10MB
logfile_backups=3
loglevel=info

[unix_http_server]
file=/tmp/supervisor.sock

[rpcinterface:supervisor]
supervisor.rpcinterface_factory=supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix:///tmp/supervisor.sock

# ── Main trading engine ────────────────────────────────────────
[program:lumitrade-engine]
command=python -m lumitrade.main
directory=/app
autostart=true
autorestart=true
startretries=5
startsecs=10
stopwaitsecs=30
stopasgroup=true
killasgroup=true
stdout_logfile=/var/log/lumitrade/engine.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
stderr_logfile=/var/log/lumitrade/engine.err
stderr_logfile_maxbytes=10MB
redirect_stderr=false
environment=PYTHONUNBUFFERED="1",PYTHONDONTWRITEBYTECODE="1"

# ── Health HTTP server (lightweight — separate from main engine) ─
[program:lumitrade-health]
command=python -m lumitrade.infrastructure.health_server
directory=/app
autostart=true
autorestart=true
startretries=10
stdout_logfile=/var/log/lumitrade/health.log
stdout_logfile_maxbytes=5MB
redirect_stderr=true

## 2.3 docker-compose.yml (local development)
version: "3.9"

services:
lumitrade-engine:
build:
context: ./backend
dockerfile: Dockerfile
target: runtime
ports:
- "8000:8000"
env_file:
- ./backend/.env
volumes:
- ./logs/engine:/var/log/lumitrade
restart: unless-stopped
healthcheck:
test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
interval: 30s
timeout: 10s
retries: 3
start_period: 60s

lumitrade-dashboard:
build:
context: ./frontend
dockerfile: Dockerfile
ports:
- "3000:3000"
env_file:
- ./frontend/.env.local
depends_on:
lumitrade-engine:
condition: service_healthy
restart: unless-stopped

volumes:
logs:

# 3. GitHub Actions CI/CD Pipelines
## 3.1 .github/workflows/test.yml — Run on every push and PR
name: Test Suite

on:
push:
branches: ["**"]
pull_request:
branches: [main, staging]

jobs:
backend-tests:
name: Backend Tests
runs-on: ubuntu-latest
defaults:
run:
working-directory: backend

steps:
- name: Checkout
uses: actions/checkout@v4

- name: Set up Python 3.11
uses: actions/setup-python@v5
with:
python-version: "3.11"
cache: "pip"
cache-dependency-path: backend/requirements.txt

- name: Install dependencies
run: pip install --require-hashes -r requirements.txt

- name: Lint with ruff
run: ruff check lumitrade/ tests/

- name: Type check with mypy
run: mypy lumitrade/ --ignore-missing-imports

- name: Run unit tests
run: |
pytest tests/unit/ -v \
--cov=lumitrade \
--cov-report=term-missing \
--cov-fail-under=75
env:
# Fake env vars for unit tests — no real API calls
OANDA_API_KEY_DATA: test_key_data
OANDA_API_KEY_TRADING: test_key_trading
OANDA_ACCOUNT_ID: test_account
OANDA_ENVIRONMENT: practice
ANTHROPIC_API_KEY: test_key
SUPABASE_URL: https://test.supabase.co
SUPABASE_SERVICE_KEY: test_service_key
TWILIO_ACCOUNT_SID: test_sid
TWILIO_AUTH_TOKEN: test_token
TWILIO_FROM_NUMBER: "+10000000000"
ALERT_SMS_TO: "+10000000001"
SENDGRID_API_KEY: test_sg_key
ALERT_EMAIL_TO: test@test.com
INSTANCE_ID: ci-test
TRADING_MODE: PAPER

- name: Run integration tests
run: pytest tests/integration/ -v -m "not live"
env:
OANDA_API_KEY_DATA: test_key_data
OANDA_API_KEY_TRADING: test_key_trading
OANDA_ACCOUNT_ID: test_account
OANDA_ENVIRONMENT: practice
ANTHROPIC_API_KEY: test_key
SUPABASE_URL: https://test.supabase.co
SUPABASE_SERVICE_KEY: test_service_key
TWILIO_ACCOUNT_SID: test_sid
TWILIO_AUTH_TOKEN: test_token
TWILIO_FROM_NUMBER: "+10000000000"
ALERT_SMS_TO: "+10000000001"
SENDGRID_API_KEY: test_sg_key
ALERT_EMAIL_TO: test@test.com
INSTANCE_ID: ci-test
TRADING_MODE: PAPER

- name: Secrets scan (gitleaks)
uses: gitleaks/gitleaks-action@v2
env:
GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

frontend-tests:
name: Frontend Tests
runs-on: ubuntu-latest
defaults:
run:
working-directory: frontend

steps:
- name: Checkout
uses: actions/checkout@v4

- name: Set up Node 20
uses: actions/setup-node@v4
with:
node-version: "20"
cache: "npm"
cache-dependency-path: frontend/package-lock.json

- name: Install dependencies
run: npm ci

- name: Type check
run: npm run type-check

- name: Lint
run: npm run lint

- name: Build check
run: npm run build
env:
NEXT_PUBLIC_SUPABASE_URL: https://test.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY: test_anon_key
SUPABASE_SERVICE_KEY: test_service_key

## 3.2 .github/workflows/deploy.yml — Deploy on main merge
name: Deploy to Railway

on:
push:
branches: [main]

jobs:
deploy:
name: Deploy
runs-on: ubuntu-latest
needs: []  # Runs after test.yml passes (branch protection)

steps:
- name: Checkout
uses: actions/checkout@v4

- name: Install Railway CLI
run: npm install -g @railway/cli

- name: Deploy engine to Railway
run: |
railway up --service lumitrade-engine --detach
env:
RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}

- name: Deploy dashboard to Railway
run: |
railway up --service lumitrade-dashboard --detach
env:
RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}

- name: Wait for health check
run: |
echo "Waiting 90s for Railway deployment to stabilize..."
sleep 90
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" \
https://lumitrade-engine.railway.app/health)
if [ "$HEALTH" != "200" ]; then
echo "Health check failed: $HEALTH"
exit 1
fi
echo "Deployment healthy."

- name: Notify deployment
if: always()
run: |
if [ "${{ job.status }}" == "success" ]; then
MSG="Lumitrade deployed successfully to production."
else
MSG="Lumitrade deployment FAILED. Rolling back."
fi
curl -X POST https://api.twilio.com/... \
--data-urlencode "Body=$MSG" \
-u "${{ secrets.TWILIO_SID }}:${{ secrets.TWILIO_TOKEN }}"

# 4. Railway Configuration
## 4.1 railway.toml — Engine Service
[build]
builder = "dockerfile"
dockerfilePath = "backend/Dockerfile"

[deploy]
startCommand = "/usr/bin/supervisord -n -c /etc/supervisor/conf.d/lumitrade.conf"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 5

[env]
# Set these in Railway dashboard — NEVER in this file
# OANDA_API_KEY_DATA
# OANDA_API_KEY_TRADING
# OANDA_ACCOUNT_ID
# OANDA_ENVIRONMENT
# ANTHROPIC_API_KEY
# SUPABASE_URL
# SUPABASE_SERVICE_KEY
# TWILIO_ACCOUNT_SID
# TWILIO_AUTH_TOKEN
# TWILIO_FROM_NUMBER
# ALERT_SMS_TO
# SENDGRID_API_KEY
# ALERT_EMAIL_TO
# INSTANCE_ID = "cloud-primary"
# TRADING_MODE = "PAPER"
# LOG_LEVEL = "INFO"

## 4.2 Railway Service Settings

## 4.3 GitHub Secrets Required
These secrets must be set in GitHub repository Settings → Secrets and Variables → Actions before the CI/CD pipelines will work:

Important  GitHub Secrets are separate from Railway environment variables. GitHub Secrets are used only during CI/CD pipeline execution. Railway environment variables are injected into the running container. Both sets must be configured.

# 5. Database Operations
## 5.1 Supabase Project Setup Procedure
- Go to supabase.com → New Project → Name: lumitrade-prod
- Select region: US East (matches Railway region for lowest latency)
- Save the project URL and both API keys (anon + service role) securely
- Go to SQL Editor → run: database/migrations/001_initial_schema.sql
- Run: database/migrations/002_add_indexes.sql
- Run: database/migrations/003_add_rls_policies.sql
- Go to Authentication → Providers → disable Email OTP if using magic links; enable if using password auth
- Go to Realtime → enable for tables: trades, signals, system_state, risk_events
- Go to Settings → API → copy URL and anon key to Railway env vars and frontend .env.local
- Go to Settings → Database → copy service role key to Railway env vars (NEVER to frontend)

## 5.2 Database Migration Procedure
All schema changes follow this procedure. No ad-hoc changes via Supabase dashboard in production.

# 1. Create migration file with next sequential number
touch database/migrations/004_your_description.sql

# 2. Write the migration SQL — additive only (no DROP or ALTER existing columns)

# 3. Test on staging Supabase first
psql $STAGING_DATABASE_URL < database/migrations/004_your_description.sql

# 4. Verify staging app still works

# 5. Apply to production during low-activity window (weekend early morning)
psql $PROD_DATABASE_URL < database/migrations/004_your_description.sql

# 6. Commit migration file to Git
git add database/migrations/004_your_description.sql
git commit -m "db: add [description] migration"

## 5.3 Database Backup Strategy

# 6. Monitoring & Alerting Stack
## 6.1 UptimeRobot Configuration
UptimeRobot is the primary external uptime monitor. It runs outside our infrastructure, so it catches failures that internal monitors miss (network partition, Railway outage, DNS failure).



## 6.2 Sentry Configuration
# backend/lumitrade/main.py — add at top of configure_logging()
import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration

def configure_sentry():
if not config.sentry_dsn:
return  # Skip if not configured
sentry_sdk.init(
dsn=config.sentry_dsn,
integrations=[AsyncioIntegration()],
traces_sample_rate=0.1,   # 10% of transactions
profiles_sample_rate=0.1,
environment=config.oanda_environment,  # "practice" or "live"
release=f"lumitrade@{VERSION}",
before_send=scrub_sentry_event,  # Remove sensitive data
)

def scrub_sentry_event(event, hint):
"""Remove API keys and sensitive data from Sentry events."""
# Scrub request data
if "request" in event:
event["request"].pop("headers", None)
event["request"].pop("cookies", None)
# Scrub environment vars that might appear in stack frames
for frame in event.get("exception", {}).get("values", [{}])[0]
.get("stacktrace", {}).get("frames", []):
frame.pop("vars", None)
return event

## 6.3 Log Aggregation
Logs flow from three sources and are retained at different levels:


## 6.4 Health Check Endpoint Implementation
# backend/lumitrade/infrastructure/health_server.py
# Lightweight HTTP server for /health — separate from main engine
# Runs as its own supervisord program so it stays up even if engine crashes

import asyncio
import json
from aiohttp import web
from ..infrastructure.db import DatabaseClient
from ..config import config

async def health_handler(request: web.Request) -> web.Response:
db = DatabaseClient()
await db.connect()

try:
# Read system state from DB
state = await db.select_one("system_state", {"id": "singleton"})
db_ok = True
except Exception:
state = None
db_ok = False

risk_state = state.get("risk_state", "UNKNOWN") if state else "UNKNOWN"
is_healthy = db_ok and risk_state not in ("EMERGENCY_HALT", "WEEKLY_LIMIT")

payload = {
"status":      "healthy" if is_healthy else "degraded",
"instance_id": config.instance_id,
"timestamp":   __import__("datetime").datetime.utcnow().isoformat() + "Z",
"components": {
"database":      {"status": "ok" if db_ok else "offline"},
"risk_engine":   {"status": "ok", "state": risk_state},
},
"trading": {
"mode":          config.trading_mode,
"open_positions":len(state.get("open_trades", [])) if state else 0,
"daily_pnl_usd": state.get("daily_pnl_usd", 0) if state else 0,
}
}

status_code = 200 if is_healthy else 503
return web.Response(
text=json.dumps(payload),
content_type="application/json",
status=status_code
)

async def main():
app = web.Application()
app.router.add_get("/health", health_handler)
runner = web.AppRunner(app)
await runner.setup()
site = web.TCPSite(runner, "0.0.0.0", 8000)
await site.start()
await asyncio.Event().wait()  # Run forever

if __name__ == "__main__":
asyncio.run(main())

# 7. Local Backup Setup & Failover
## 7.1 Local Machine Requirements

## 7.2 Local Backup Installation Procedure
- Clone the repository: git clone https://github.com/[you]/lumitrade
- Install Python 3.11 and create virtual environment: python3.11 -m venv .venv
- Activate venv and install dependencies: pip install --require-hashes -r backend/requirements.txt
- Create backend/.env file with ALL production environment variables
- Set INSTANCE_ID=local-backup in the .env file
- Set TRADING_MODE=PAPER initially — switch to LIVE only after cloud primary is confirmed live
- Add local machine IP to OANDA API whitelist (Settings → Manage API Access)
- Test connection: python -c "from lumitrade.config import config; print(config.oanda_environment)"
- Test manual run: python -m lumitrade.main — verify it starts, acquires STANDBY lock (not primary), and begins monitoring
- Set up auto-start on boot (see Section 7.3)

## 7.3 Auto-Start on Boot
### Option A: macOS LaunchAgent
# ~/Library/LaunchAgents/com.lumitrade.backup.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
<key>Label</key>
<string>com.lumitrade.backup</string>
<key>ProgramArguments</key>
<array>
<string>/path/to/lumitrade/.venv/bin/python</string>
<string>-m</string>
<string>lumitrade.main</string>
</array>
<key>WorkingDirectory</key>
<string>/path/to/lumitrade/backend</string>
<key>EnvironmentVariables</key>
<dict>
<key>INSTANCE_ID</key><string>local-backup</string>
</dict>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>StandardOutPath</key>
<string>/path/to/lumitrade/logs/local-backup.log</string>
<key>StandardErrorPath</key>
<string>/path/to/lumitrade/logs/local-backup.err</string>
</dict>
</plist>

# Load it:
launchctl load ~/Library/LaunchAgents/com.lumitrade.backup.plist

### Option B: Linux systemd
# /etc/systemd/system/lumitrade-backup.service
[Unit]
Description=Lumitrade Local Backup Instance
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=lumitrade
WorkingDirectory=/home/lumitrade/lumitrade/backend
ExecStart=/home/lumitrade/lumitrade/.venv/bin/python -m lumitrade.main
Restart=on-failure
RestartSec=15
Environment=INSTANCE_ID=local-backup
EnvironmentFile=/home/lumitrade/lumitrade/backend/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target

# Enable and start:
sudo systemctl enable lumitrade-backup
sudo systemctl start lumitrade-backup
sudo systemctl status lumitrade-backup

## 7.4 Failover Protocol — Distributed Lock Implementation
# backend/lumitrade/state/lock.py
import asyncio
from datetime import datetime, timezone, timedelta
from ..infrastructure.db import DatabaseClient
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

LOCK_TTL_SECONDS  = 120   # Lock expires if not renewed
RENEW_INTERVAL    = 60    # Renew every 60s
TAKEOVER_THRESHOLD = 180  # Take over if lock age > 3 minutes

class DistributedLock:
"""Primary instance lock using Supabase system_state table."""

def __init__(self, db: DatabaseClient):
self.db = db

async def acquire(self, instance_id: str) -> bool:
"""Try to become primary. Returns True if successful."""
now = datetime.now(timezone.utc)
expiry = now + timedelta(seconds=LOCK_TTL_SECONDS)

# Check current lock state
state = await self.db.select_one("system_state", {"id": "singleton"})
if not state:
return False

current_expires = state.get("lock_expires_at")
current_holder  = state.get("instance_id")

# Lock is free or expired or we already hold it
lock_expired = (not current_expires or
datetime.fromisoformat(current_expires) < now)
we_hold_it   = (current_holder == instance_id)

if not lock_expired and not we_hold_it:
logger.info("lock_not_acquired_primary_exists",
holder=current_holder)
return False

# Acquire the lock
await self.db.update("system_state",
{"id": "singleton"},
{
"instance_id":       instance_id,
"is_primary_instance": True,
"lock_expires_at":   expiry.isoformat(),
"updated_at":        now.isoformat(),
}
)
logger.info("lock_acquired", instance_id=instance_id)
return True

async def renew_loop(self, instance_id: str):
"""Background task — renew lock every RENEW_INTERVAL seconds."""
consecutive_failures = 0
while True:
await asyncio.sleep(RENEW_INTERVAL)
try:
now    = datetime.now(timezone.utc)
expiry = now + timedelta(seconds=LOCK_TTL_SECONDS)
await self.db.update("system_state",
{"id": "singleton", "instance_id": instance_id},
{"lock_expires_at": expiry.isoformat(),
"updated_at":      now.isoformat()}
)
consecutive_failures = 0
except Exception as e:
consecutive_failures += 1
logger.error("lock_renewal_failed",
error=str(e),
consecutive=consecutive_failures)
if consecutive_failures >= 2:
logger.critical("lock_renewal_repeated_failure_shutting_down")
raise SystemExit(1)

async def release(self, instance_id: str):
"""Release lock on graceful shutdown."""
await self.db.update("system_state",
{"id": "singleton", "instance_id": instance_id},
{"is_primary_instance": False,
"lock_expires_at":     None,
"instance_id":         None}
)
logger.info("lock_released", instance_id=instance_id)

# 8. Secrets Rotation Procedure
## 8.1 90-Day Key Rotation Schedule
All API keys must be rotated every 90 days. The rotation procedure is designed to achieve zero downtime.


## 8.2 Rotation Calendar
# Track in a simple text file committed to a PRIVATE repo
# keys-rotation-log.txt (in private notes — never commit API keys)

OANDA_DATA key:         Last rotated: 2026-03-20  Next due: 2026-06-18
OANDA_TRADING key:      Last rotated: 2026-03-20  Next due: 2026-06-18
ANTHROPIC key:          Last rotated: 2026-03-20  Next due: 2026-06-18
TWILIO token:           Last rotated: 2026-03-20  Next due: 2026-06-18
SENDGRID key:           Last rotated: 2026-03-20  Next due: 2026-06-18

# Set reminders in your calendar 1 week before each due date

# 9. Pre-Go-Live DevOps Checklist
## 9.1 Infrastructure Readiness Checklist
Complete every item below before switching to TRADING_MODE=LIVE and depositing real capital.


# 10. Operational Runbook
## 10.1 Daily Operations (5 minutes)
- Check daily performance email at 6pm EST — review P&L, trade count, win rate
- Open dashboard — verify system status panel shows all green
- Check Railway logs for any ERROR or CRITICAL entries
- Check Sentry dashboard — zero new issues is the goal
- Verify open positions are managed (SL/TP attached, no orphaned trades)

## 10.2 Weekly Operations (30 minutes)
- Run performance review: analytics page → last 7 days → record in trading journal
- Review AI signal quality: signals page → count HOLD vs BUY/SELL ratio
- Check Supabase storage usage — alert if > 400MB (free tier limit 500MB)
- Review Railway billing — confirm within expected range
- Pull latest code: git pull origin main on local backup machine
- Check rotation calendar — any keys due within 2 weeks?

## 10.3 Incident Response Playbook
### Scenario 1: System not trading (signals not generating)
- Check Railway logs for ERROR entries in last 60 minutes
- Check /health endpoint — identify which component is failing
- If OANDA API: check OANDA system status at oandastatus.com
- If AI Brain: check Anthropic status at status.anthropic.com
- If Database: check Supabase status at status.supabase.com
- If all external services OK: check circuit breaker state in system_state table
- If circuit breaker OPEN: wait for auto-reset (30s) or manually reset via: UPDATE system_state SET circuit_breaker_state='CLOSED'

### Scenario 2: Ghost/phantom trade detected (CRITICAL alert received)
- IMMEDIATELY check OANDA portal for actual open positions
- Compare OANDA positions to Lumitrade dashboard open positions
- If OANDA has a trade Lumitrade does not know about: manually close it in OANDA portal immediately
- After closing: check system_events table for the PHANTOM_TRADE log
- Do NOT restart the system until you understand why the phantom trade exists
- Review git history and logs from the time period when the trade was opened

### Scenario 3: Daily loss limit hit (-5%)
- This is expected behavior — the system halted correctly
- Review the trades that caused the loss in the dashboard
- Check if the losses were normal (market moved against signals) or anomalous (bug, data corruption)
- If normal: the system will auto-resume the next trading session. No action needed.
- If anomalous: activate kill switch, investigate root cause before resuming

### Scenario 4: Cloud server down, local backup active
- Receive CRITICAL SMS: "LOCAL BACKUP ACTIVATED"
- Check Railway dashboard for service status
- If Railway incident: monitor Railway status page, wait for resolution
- While local backup is active: monitor it via: ssh into local machine and check logs
- When Railway recovers: cloud instance restarts and acquires primary lock automatically
- Local backup detects it lost primary lock and gracefully stops trading
- Verify via dashboard that cloud is primary again and all positions are reconciled



END OF DOCUMENT
Lumitrade DevOps Specification v1.0  |  Confidential
Next Document: Security Specification (Role 6)





LUMITRADE
DevOps Specification

ROLE 5 — SENIOR DEVOPS ENGINEER
All original infrastructure + future feature environment variables
Version 2.0  |  Includes future feature foundations
Date: March 21, 2026




# 1–10. All Original DOS Sections
All original DevOps Specification content is unchanged: infrastructure overview, Docker configuration, GitHub Actions CI/CD, Railway configuration, database operations, monitoring stack, local backup setup, secrets rotation, pre-go-live checklist, and operational runbook.
Reference  Original DOS v1.0 is the authoritative source for all Phase 0 infrastructure. This document adds Section 11 only.

# 11. Future Feature Infrastructure
## 11.1 Extended Environment Variables
All future feature environment variables are optional. When absent, the feature stub returns safe defaults. When present, the feature becomes active. Add these to .env.example and Railway env vars when ready to activate each feature.


## 11.2 Updated .env.example
Add this section to the .env.example template:

# ── Future features (optional — absence = feature inactive) ──

# F-01: Multi-model AI brain (Phase 2)
# OPENAI_API_KEY=sk-proj-your-key-here

# F-03 + F-11: News sentiment + intelligence reports (Phase 2)
# NEWS_API_KEY=your-newsapi-key

# F-06 + F-07: Marketplace + copy trading payments (Phase 3)
# STRIPE_SECRET_KEY=sk_live_your-key
# STRIPE_CONNECT_CLIENT_ID=ca_your-connect-id

# F-09: Multi-asset expansion (Phase 3)
# COINBASE_API_KEY=your-coinbase-key
# COINBASE_API_SECRET=your-coinbase-secret
# ALPACA_API_KEY=your-alpaca-key
# ALPACA_API_SECRET=your-alpaca-secret

# F-10: Native mobile app push (Phase 3)
# EXPO_PUSH_TOKEN=ExponentPushToken[...]

## 11.3 Feature Flag System
Add a lightweight feature flag system to config.py. Flags are derived from whether the relevant env var is present — no separate configuration needed:

# In config.py — add to LumitradeConfig class

@property
def features(self) -> dict[str, bool]:
"""Derive feature flags from environment variable presence."""
return {
"multi_model_ai":    bool(getattr(self, "openai_api_key", None)),
"news_sentiment":    bool(getattr(self, "news_api_key", None)),
"intelligence_report": bool(getattr(self, "news_api_key", None)),
"marketplace":       bool(getattr(self, "stripe_secret_key", None)),
"copy_trading":      bool(getattr(self, "stripe_secret_key", None)),
"crypto":            bool(getattr(self, "coinbase_api_key", None)),
"stocks":            bool(getattr(self, "alpaca_api_key", None)),
"mobile_push":       bool(getattr(self, "expo_push_token", None)),
}

# Usage in any module:
if config.features["news_sentiment"]:
sentiment = await self.sentiment_analyzer.analyze(currencies)
else:
sentiment = {c: CurrencySentiment.NEUTRAL for c in currencies}


## SMS Provider: Telnyx (Replaces Twilio)
Note: The original DOS v1.0 referenced Twilio for SMS alerts. Telnyx replaces Twilio in all environments. The infrastructure is identical — only the credentials change.
### Environment Variable Changes
Remove these three Twilio variables:
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_FROM_NUMBER
Replace with these two Telnyx variables:
TELNYX_API_KEY=KEY0123...      # From Telnyx portal -> API Keys
TELNYX_FROM_NUMBER=+1XXXXXXXXXX  # Your Telnyx number
ALERT_SMS_TO=+1XXXXXXXXXX        # Your personal phone (unchanged)
### requirements.txt Change
Remove: twilio==8.13.0
No replacement needed — alert_service.py uses raw httpx (already in stack).
All other DOS sections (Docker, Railway, GitHub Actions, monitoring, runbook) are unchanged. The SMS infrastructure is identical — only the API endpoint and credentials differ.

# 12. Subagent Infrastructure
The subagent system requires minimal infrastructure changes. All subagents share the existing Anthropic API key and Supabase connection. Only SA-04 requires an additional API key.
## 12.1 Additional Environment Variables
# SA-03: Risk Monitor — enable/disable flag
# RISK_MONITOR_ENABLED=false   # Set to true in Phase 2 to activate SA-03

# SA-04: Intelligence Subagent — requires news API
# NEWS_API_KEY=your-newsapi-key  # From newsapi.org (already in future vars)

# No additional env vars needed for SA-01, SA-02, or SA-05
# They use the existing ANTHROPIC_API_KEY
## 12.2 Scheduler Additions to main.py
# Add to OrchestratorService._start_tasks():

# SA-03: Risk Monitor — every 30 minutes
asyncio.create_task(self._risk_monitor_loop(), name="risk_monitor")

# SA-04: Intelligence — weekly, Sunday 19:00 EST
asyncio.create_task(self._weekly_intelligence_loop(), name="intelligence")

async def _risk_monitor_loop(self):
"""Runs SA-03 every 30 minutes while positions are open."""
while True:
await asyncio.sleep(1800)  # 30 minutes
try:
open_trades = await self.state.get_open_trades()
if open_trades:
market_data = await self.data_engine.get_current_snapshot()
await self.subagents.run_risk_monitor(open_trades, market_data)
except Exception as e:
logger.warning("risk_monitor_loop_error", error=str(e))

async def _weekly_intelligence_loop(self):
"""Fires SA-04 every Sunday at 19:00 EST."""
while True:
now = datetime.now(timezone.utc)
# Calculate seconds until next Sunday 19:00 EST (00:00 UTC Monday)
days_ahead = (6 - now.weekday()) % 7
next_sunday = now.replace(hour=0, minute=0, second=0) + timedelta(days=days_ahead)
wait_seconds = (next_sunday - now).total_seconds()
await asyncio.sleep(max(wait_seconds, 60))
try:
await self.subagents.run_weekly_intelligence(self.config.account_id)
except Exception as e:
logger.warning("intelligence_loop_error", error=str(e))
## 12.3 API Cost Impact
Phase 0 subagent cost: $0/day (all stubs — no API calls made)

Phase 2 estimated daily cost (personal use):
SA-01 Market Analyst:   3 pairs x 96 scans = 288 calls x $0.002 = $0.58/day
SA-02 Post-Trade:       ~5 trades/day x $0.003 = $0.015/day
SA-03 Risk Monitor:     ~8 fires/day x $0.002 = $0.016/day
SA-04 Intelligence:     1/week x $0.02 = $0.003/day
SA-05 Onboarding:       Phase 3 only
TOTAL:                  ~$0.61/day additional

Phase 2 SaaS cost per user: ~$0.61/day = ~$18.30/month
Covered by: $49-79/month subscription. Profitable per user.

| Attribute | Value |
|---|---|
| Document | DevOps Specification (DOS) |
| Preceding | PRD v1.0 + SAS v1.0 + BDS v1.0 + FDS v1.0 |
| Role | Senior DevOps Engineer |
| Primary cloud platform | Railway.app |
| Container runtime | Docker (python:3.11-slim) |
| CI/CD | GitHub Actions |
| Database | Supabase (managed PostgreSQL) |
| Monitoring | UptimeRobot + Sentry + structured logs |
| Next document | Security Specification (Role 6) |


| Environment | Purpose | Deploy Trigger |
|---|---|---|
| Development | Local machine. .env file. Supabase project (shared or dev). No Supervisord. | Manual: python -m lumitrade.main |
| Staging | Railway service (separate from prod). Same Docker image. Staging Supabase project. Paper trading only. | Push to staging branch → auto-deploy |
| Production | Railway service. Production Supabase. PAPER or LIVE trading mode. | Merge to main + all tests pass → auto-deploy |
| Local Backup | Developer machine or Raspberry Pi. Production Supabase. Standby mode — activates on cloud failure only. | Manual: python -m lumitrade.main (runs as standby) |


| Service | Platform | Role |
|---|---|---|
| lumitrade-engine | Railway (Docker container) | Python trading bot — primary cloud instance |
| lumitrade-dashboard | Railway (Next.js) | Web dashboard — served to operator |
| lumitrade-db | Supabase | PostgreSQL database + Realtime + Auth |
| lumitrade-engine-local | Developer machine | Local backup — standby monitoring only |
| uptime-monitor | UptimeRobot | Pings /health every 60s — SMS on failure |
| error-tracker | Sentry | Crash reports + stack traces |
| sms-alerts | Twilio | Trade and critical system SMS notifications |
| email-alerts | SendGrid | Daily performance digest + warning emails |


| Service | Tier | Est. Monthly Cost |
|---|---|---|
| Railway.app (engine + dashboard) | Hobby ($5 credit) | $5–10 |
| Supabase | Free (500MB, 2GB bandwidth) | $0 |
| Anthropic Claude API | Pay-as-you-go (~500 calls/day) | $10–25 |
| Twilio SMS | Pay-as-you-go (~50 SMS/month) | $1–3 |
| SendGrid | Free (100 emails/day) | $0 |
| UptimeRobot | Free (50 monitors) | $0 |
| Sentry | Free (5K errors/month) | $0 |
| GitHub Actions | Free (2000 min/month) | $0 |
| Domain (lumitrade.app or .io) | Annual | $10–15/year |
| Total Phase 0 | — | $16–38/month |


| Setting | Value / Configuration |
|---|---|
| Region | US-East (us-east-1) — lowest latency to OANDA US servers |
| Plan | Hobby ($5/month) for Phase 0. Upgrade to Pro before live trading at scale. |
| Memory | 512MB (Hobby). Upgrade to 1GB if pandas operations cause OOM. |
| CPU | Shared (Hobby). Dedicated on Pro when needed. |
| Deploy on push | Enabled. Source: GitHub main branch. |
| Health check path | /health — must return 200 OK |
| Health check timeout | 30 seconds |
| Restart policy | On failure. Max 5 retries before alerting. |
| Logs retention | 7 days on Railway. Also streamed to Supabase system_events for permanent retention of ERROR+. |
| Custom domain | lumitrade-engine.lumitrade.app (configure after domain purchase) |
| Environment isolation | Production and Staging are separate Railway services with separate env vars and separate Supabase projects. |


| Secret Name | Value Source |
|---|---|
| RAILWAY_TOKEN | Railway dashboard → Account → Tokens → Create token |
| TWILIO_SID | Twilio Console → Account SID (for deploy notifications) |
| TWILIO_TOKEN | Twilio Console → Auth Token |
| TWILIO_FROM | Twilio phone number for deploy notifications |
| TWILIO_TO | Your phone number for deploy notifications |


| Backup Type | Frequency / Retention |
|---|---|
| Supabase automatic backups | Daily. 7-day retention on Free tier. 30-day on Pro. Enabled by default — no action required. |
| Manual export before migrations | Run before every production migration: Settings → Database → Backups → Create backup |
| Trade history export | Monthly CSV export via dashboard. Store locally and in Google Drive. |
| System state snapshot | Automatically persisted to system_state table every 30s by the Python engine. |


| Monitor | URL / Target |
|---|---|
| Engine health | https://lumitrade-engine.railway.app/health → expect 200 OK |
| Dashboard health | https://lumitrade-dashboard.railway.app → expect 200 OK |
| Local backup health (if available) | http://[local-ip]:8000/health → expect 200 OK |


| Setting | Value |
|---|---|
| Check interval | Every 5 minutes (free tier maximum) |
| Alert contacts | SMS to operator phone + email |
| Alert conditions | Down: immediately. Recovery: after 2 successful checks. |
| Maintenance window | Saturday 00:00–06:00 EST (forex market closed) |
| Keyword check | /health response must contain: "status":"healthy" |


| Log Source | Destination | Retention |
|---|---|---|
| Python engine stdout (all levels) | Railway log viewer (streaming) | 7 days rolling |
| ERROR + CRITICAL events | Supabase system_events table (via logger) | Indefinite |
| Sentry captures | Sentry dashboard | 90 days (free tier) |
| Trade + signal records | Supabase trades + signals tables | Indefinite |
| Alert delivery log | Supabase alerts_log table | Indefinite |
| Execution API calls | Supabase execution_log table | 30 days then archive |


| Requirement | Specification |
|---|---|
| Hardware options | Laptop (no-sleep configured), Raspberry Pi 4 (2GB RAM min), Mac Mini, any always-on x86/ARM64 machine |
| OS | Ubuntu 22.04 LTS, macOS 13+, or Raspberry Pi OS (64-bit) |
| Python | 3.11+ — same version as production |
| Network | Stable internet connection. Static IP preferred (for OANDA IP whitelist). |
| Power | UPS (uninterruptible power supply) strongly recommended for true failover capability |
| Storage | 10GB minimum free space for logs and Python environment |


| Key | Rotation Procedure |
|---|---|
| OANDA_API_KEY_DATA | 1. Create new read-only key in OANDA portal. 2. Add new IP whitelist entries. 3. Update Railway env var. 4. Redeploy. 5. Confirm data flowing. 6. Delete old key from OANDA. |
| OANDA_API_KEY_TRADING | Same as above. Extra caution: confirm no open trades before rotating. Consider paper mode during rotation. |
| ANTHROPIC_API_KEY | 1. Create new key at console.anthropic.com. 2. Update Railway env var. 3. Redeploy. 4. Confirm AI signals generating. 5. Delete old key. |
| SUPABASE_SERVICE_KEY | 1. Go to Supabase Settings → API → Reveal service role key → Cannot rotate directly. Generate new project JWT secret in advanced settings. 2. Update all consumers simultaneously. 3. Test immediately. |
| TWILIO_AUTH_TOKEN | 1. Twilio Console → Account → Auth Tokens → Create secondary. 2. Update Railway env var. 3. Redeploy. 4. Confirm SMS delivery. 5. Promote secondary to primary. 6. Delete old. |
| SENDGRID_API_KEY | 1. Create new key in SendGrid. 2. Update Railway env var. 3. Redeploy. 4. Send test email. 5. Delete old key. |


| Item | How to Verify | Status |
|---|---|---|
| Railway engine service deployed and healthy | GET /health returns 200 with status:healthy | [ ] |
| Railway dashboard service deployed | Dashboard URL loads and shows data | [ ] |
| Supabase all migrations applied | Check table list in Supabase dashboard | [ ] |
| Supabase RLS policies active | Try accessing tables with anon key — should fail without auth | [ ] |
| Supabase Realtime enabled for all tables | Dashboard signals update without page refresh | [ ] |
| OANDA practice account connected | Account balance shows in dashboard | [ ] |
| OANDA API key IP whitelist configured | Test from non-whitelisted IP — should fail | [ ] |
| Paper trading running 7+ days | Trade history shows 50+ paper trades | [ ] |
| Win rate >= 40% on paper trades | Analytics page confirms metric | [ ] |
| No system crashes in 7-day paper run | system_events table has no CRASH events | [ ] |
| Kill switch tested and confirmed | Activate in paper mode — verify all signals halt | [ ] |
| Daily loss limit tested | Manually set daily P&L to -5% — verify trading halts | [ ] |
| Crash recovery tested | Kill -9 the process — verify restart < 60s and reconciliation | [ ] |
| Local backup tested | Stop cloud service — verify local takeover within 3 min | [ ] |
| Dual-instance prevention verified | Start two instances — verify only one becomes primary | [ ] |
| UptimeRobot configured and alerting | Take down service — verify SMS received | [ ] |
| Sentry receiving events | Trigger a test error — confirm Sentry captures it | [ ] |
| SMS alerts working | Force a DAILY_LIMIT event — confirm SMS received | [ ] |
| Daily email working | Wait for 18:00 EST email — confirm received | [ ] |
| All secrets rotated before go-live | Rotation log updated with go-live dates | [ ] |
| Git history scanned for secrets | gitleaks scan on full repo history passes | [ ] |
| GitHub branch protection on main | Direct push to main blocked — PR required | [ ] |
| Initial capital set to $100 max | OANDA account funded with $100 only | [ ] |
| Risk per trade set to 0.5% max | Settings panel confirms 0.5% risk setting | [ ] |
| TRADING_MODE switched to LIVE | Railway env var updated + redeployed | [ ] |


| Attribute | Value |
|---|---|
| Version | 2.0 — extended environment variables for all 15 future features |
| New env vars | 11 additional optional variables for future integrations |
| Behavioral change | Zero — optional vars absent = features inactive |
| Infrastructure changes | Zero — same Railway + Supabase + Docker stack |


| Variable | Feature | When to Add |
|---|---|---|
| OPENAI_API_KEY | F-01: Multi-Model AI Brain | Phase 2 — when activating consensus engine |
| NEWS_API_KEY | F-03: News Sentiment AI + F-11: Intelligence Report | Phase 2 — when activating sentiment analysis |
| BENZINGA_API_KEY | F-03: Alternative news source | Phase 2 — optional premium news feed |
| EXPO_PUSH_TOKEN | F-10: Native Mobile App | Phase 3 — when building React Native app |
| ONESIGNAL_APP_ID | F-10: Alternative push service | Phase 3 — optional push provider |
| STRIPE_SECRET_KEY | F-06: Strategy Marketplace + F-07: Copy Trading | Phase 3 — when activating payments |
| STRIPE_CONNECT_CLIENT_ID | F-06: Creator payouts | Phase 3 — for strategy creator revenue sharing |
| COINBASE_API_KEY | F-09: Crypto expansion | Phase 3 — when adding crypto asset class |
| ALPACA_API_KEY | F-09: Stocks expansion | Phase 3 — when adding US stocks |
| TASTYTRADE_API_KEY | F-09: Options expansion | Phase 4 — when adding options trading |
| INVESTOR_REPORT_EMAIL | F-15: Lumitrade Fund | Phase 4 — fund investor email list |
