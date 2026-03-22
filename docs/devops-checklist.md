# Lumitrade Pre-Go-Live DevOps Checklist

Complete every item below before switching to `TRADING_MODE=LIVE` and depositing real capital.

Source: DOS v2.0 Section 9.1

---

## Railway Deployment

- [ ] Railway engine service deployed and healthy -- `GET /health` returns 200 with `status:healthy`
- [ ] Railway dashboard service deployed -- Dashboard URL loads and shows data
- [ ] Railway region configured to US East (lowest latency to OANDA/Supabase)

## Database (Supabase)

- [ ] All database migrations applied -- Check table list in Supabase dashboard matches expected 7+ tables
- [ ] Supabase RLS policies active -- Try accessing tables with anon key without auth, should fail
- [ ] Supabase Realtime enabled for key tables -- Dashboard signals update without page refresh
- [ ] Supabase storage usage confirmed within free tier limits (< 500MB)

## Process Management

- [ ] Supervisord managing 2 processes (engine + health server) -- `supervisorctl status` shows both RUNNING
- [ ] Crash recovery via Supervisord -- `kill -9` engine process, confirm auto-restart within 60s

## OANDA Integration

- [ ] OANDA practice account connected -- Account balance shows in dashboard
- [ ] OANDA API key IP whitelist configured -- Test from non-whitelisted IP confirms rejection
- [ ] OANDA live account ready with $100 max initial capital

## CI/CD Pipeline

- [ ] GitHub Actions CI/CD passing on push to main -- All test suites green
- [ ] GitHub branch protection on main -- Direct push to main blocked, PR required
- [ ] Critical test runner script (`scripts/run_critical_tests.sh`) executes successfully

## Monitoring and Alerting

- [ ] UptimeRobot configured -- Pings `/health` every 5 minutes, SMS alerts on failure
- [ ] UptimeRobot alerting verified -- Take down service, confirm SMS received
- [ ] Sentry receiving error events -- Trigger a test error, confirm Sentry captures it
- [ ] Sentry `before_send` scrubber confirmed (no sensitive data in error reports)
- [ ] SMS alerts working -- Force a DAILY_LIMIT event, confirm SMS received via Twilio
- [ ] Daily performance email working -- Wait for 18:00 EST email, confirm received

## Paper Trading Validation

- [ ] Paper trading running 7+ consecutive days without crash
- [ ] Trade history shows 50+ paper trades across all 3 currency pairs
- [ ] Win rate >= 40% on paper trades -- Analytics page confirms metric
- [ ] No system crashes in 7-day paper run -- `system_events` table has zero CRASH events

## Kill Switch and Safety

- [ ] Kill switch tested and confirmed -- Activate in paper mode, verify all signals halt within 10s
- [ ] Daily loss limit tested -- Manually set daily P&L to -5%, verify trading halts
- [ ] Crash recovery tested -- `kill -9` the process, verify restart < 60s and reconciliation correct
- [ ] Local backup tested -- Stop cloud service, verify local takeover within 3 minutes
- [ ] Dual-instance prevention verified -- Start two instances, verify only one becomes primary

## Secrets and Security

- [ ] All secrets rotated before go-live -- Rotation log updated with go-live dates
- [ ] Git history scanned for secrets -- `gitleaks detect --source . --log-opts="--all"` passes clean
- [ ] All environment variables set in Railway dashboard (not in code)
- [ ] Key rotation calendar created with 90-day rotation schedule

## Local Backup

- [ ] Local backup machine configured with latest code
- [ ] Local backup health endpoint accessible -- `http://[local-ip]:8000/health` returns 200
- [ ] Failover tested -- Cloud stopped, local activates within 3 minutes

## Log and Data Retention

- [ ] Railway log retention confirmed (7 days rolling)
- [ ] ERROR+ events streamed to Supabase `system_events` table for permanent retention
- [ ] Sentry retention confirmed (90 days on free tier)

## Final Go-Live Steps (execute in order)

- [ ] All items above checked and verified
- [ ] All 13 Go/No-Go gates passed (see docs/go-no-go-gates.md)
- [ ] 27-item security audit complete (see docs/security-audit.md)
- [ ] Risk per trade set to 0.5% max for first 2 weeks
- [ ] Initial capital set to $100 max
- [ ] `TRADING_MODE` switched to `LIVE` in Railway env var
- [ ] Redeployed with LIVE mode -- confirm engine starts in live mode via logs

---

## Summary

| Category | Items |
|----------|-------|
| Railway Deployment | 3 |
| Database (Supabase) | 4 |
| Process Management | 2 |
| OANDA Integration | 3 |
| CI/CD Pipeline | 3 |
| Monitoring and Alerting | 6 |
| Paper Trading Validation | 4 |
| Kill Switch and Safety | 5 |
| Secrets and Security | 4 |
| Local Backup | 3 |
| Log and Data Retention | 3 |
| Final Go-Live Steps | 7 |
| **Total** | **47** |
