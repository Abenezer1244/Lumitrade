# Lumitrade Pre-Deployment Checklist

Complete every item before deploying to Railway for paper trading.

Source: DOS v2.0 Section 9.1

---

## CI/CD Pipeline

- [ ] All tests pass (CI green on main branch)
- [ ] `gitleaks detect --source . --log-opts="--all"` passes clean
- [ ] `ruff check .` passes with zero errors
- [ ] `mypy lumitrade/` passes with zero errors
- [ ] Frontend `tsc --noEmit` and `npm run lint` pass

## Security Audit

- [ ] Security audit complete (all 27 items in `docs/security-audit.md`)
- [ ] No secrets in git history (gitleaks full scan)
- [ ] pre-commit hook installed and tested

## Environment Variables Set in Railway

### Required (backend will not start without these)

- [ ] `OANDA_API_KEY_DATA` -- Read-only key for data fetching
- [ ] `OANDA_API_KEY_TRADING` -- Trading key for ExecutionEngine only
- [ ] `OANDA_ACCOUNT_ID` -- OANDA account ID
- [ ] `OANDA_ENVIRONMENT=practice` -- Must be `practice` until go-live
- [ ] `ANTHROPIC_API_KEY` -- Claude API key
- [ ] `SUPABASE_URL` -- Supabase project URL
- [ ] `SUPABASE_SERVICE_KEY` -- Server-side service role key
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY` -- Browser-safe anon key (frontend)
- [ ] `INSTANCE_ID=cloud-primary` -- Identifies this as the cloud instance
- [ ] `TRADING_MODE=PAPER` -- MUST be PAPER until all 13 go/no-go gates pass
- [ ] `LOG_LEVEL=INFO`

### Alerts (required for monitoring)

- [ ] `TELNYX_API_KEY` -- SMS alerts via Telnyx
- [ ] `TELNYX_FROM_NUMBER` -- Your Telnyx phone number
- [ ] `ALERT_SMS_TO` -- Your personal phone number
- [ ] `SENDGRID_API_KEY` -- Email alerts via SendGrid
- [ ] `ALERT_EMAIL_TO` -- Your email address

### Optional

- [ ] `SENTRY_DSN` -- Error tracking (strongly recommended)

## Railway Service Configuration

- [ ] Railway project created
- [ ] Backend service linked to GitHub repo (auto-deploy on push to main)
- [ ] Build config: Dockerfile at `backend/Dockerfile`
- [ ] Health check path: `/health`
- [ ] Health check timeout: 300 seconds
- [ ] Restart policy: ON_FAILURE, max 5 retries
- [ ] Region: US East (lowest latency to OANDA and Supabase)

## Frontend Deployment

- [ ] Frontend deployed as separate Railway service (or Vercel)
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY` set in frontend env vars
- [ ] `NEXT_PUBLIC_SUPABASE_URL` set in frontend env vars
- [ ] Frontend loads and displays dashboard

## Database (Supabase)

- [ ] Supabase project created
- [ ] All database migrations applied (7+ tables created)
- [ ] RLS policies active on all tables
- [ ] Realtime enabled for signals and trades tables
- [ ] Service key confirmed NOT in frontend code

## Health Endpoint

- [ ] `GET /health` returns HTTP 200 with `{"status":"healthy"}`
- [ ] Health response includes database connectivity status
- [ ] Health response includes broker connectivity status

## OANDA

- [ ] Practice account created at developer.oanda.com
- [ ] Two API keys generated (data read-only + trading)
- [ ] Account balance visible in dashboard
- [ ] IP whitelist configured (if supported by plan)

## Paper Trading Mode Confirmed

- [ ] `TRADING_MODE=PAPER` confirmed in Railway env vars
- [ ] Engine logs show `trading_mode=PAPER` on startup
- [ ] Paper executor active (not OANDA live executor)

## Safety Systems

- [ ] Kill switch tested in paper mode (all signals halt within 10 seconds)
- [ ] Daily loss limit tested (-5% triggers halt)
- [ ] Crash recovery tested (`kill -9` engine, auto-restart within 60 seconds)

## Monitoring

- [ ] UptimeRobot configured to ping `/health` every 5 minutes
- [ ] UptimeRobot alert contacts configured (email)
- [ ] Sentry DSN configured and receiving test events
- [ ] Telnyx SMS alerts tested (force a CRITICAL event)
- [ ] SendGrid daily email tested

## Local Backup (if applicable)

- [ ] Local machine has latest Docker image
- [ ] `INSTANCE_ID=local-backup` set in local `.env`
- [ ] DistributedLock failover tested (cloud stops, local takes over within 3 minutes)
- [ ] Local health endpoint accessible

---

## Post-Deployment Verification

After deploying, run the verification script:

```bash
HEALTH_URL=https://<your-app>.railway.app/health ./scripts/verify_deployment.sh
```

Then start the daily runbook (see `docs/MONITORING.md`).
