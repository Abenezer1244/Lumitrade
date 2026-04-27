# Lumitrade Monitoring Configuration

Source: DOS v2.0

---

## UptimeRobot Setup

### Health Endpoint Monitor

1. Create a free account at [uptimerobot.com](https://uptimerobot.com)
2. Add a new monitor:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** Lumitrade Engine Health
   - **URL:** `https://<your-railway-app>.railway.app/health`
   - **Monitoring Interval:** 5 minutes (default)
   - **HTTP Method:** GET
   - **Expected Status Code:** 200
3. Enable keyword monitoring (optional):
   - **Keyword Type:** Keyword Exists
   - **Keyword Value:** `"status":"healthy"`

### Critical Period Monitoring

During the first 2 weeks of live trading or immediately after deployments, increase monitoring frequency:

- **Monitoring Interval:** 1 minute
- Revert to 5 minutes after the critical period passes

---

## What to Monitor

### Primary: `/health` Endpoint

The health server (aiohttp on port 8000) returns a JSON payload:

```json
{
  "status": "healthy",
  "instance_id": "cloud-primary",
  "trading_mode": "PAPER",
  "uptime_seconds": 86400,
  "database": "connected",
  "broker": "connected",
  "last_heartbeat": "2026-03-22T12:00:00Z"
}
```

**What each field tells you:**

| Field | Healthy Value | Action if Unhealthy |
|-------|--------------|---------------------|
| `status` | `healthy` | Check Railway logs immediately |
| `database` | `connected` | Check Supabase status page, verify `SUPABASE_URL` env var |
| `broker` | `connected` | Check OANDA status, verify API keys |
| `uptime_seconds` | Increasing over time | If resets frequently, check for crash loops in supervisord |
| `last_heartbeat` | Within last 60 seconds | If stale, engine process may be hung |

### Secondary: Response Time

- **Target p95 response time:** < 500ms for `/health`
- **Alert threshold:** > 2000ms sustained over 3 checks
- Response time spikes may indicate resource exhaustion on Railway

### Tertiary: Error Rate

- Track via Sentry dashboard
- **Target:** < 1 error per hour during normal operation
- **Alert threshold:** > 10 errors in 5 minutes (indicates systemic failure)

---

## Alert Channels

### Email (Primary -- Active Now)

- **SendGrid** delivers the daily performance email at 18:00 EST
- **UptimeRobot** sends downtime alerts to `ALERT_EMAIL_TO`
- Configure UptimeRobot alert contacts:
  1. My Alerts > Add Alert Contact
  2. Type: Email
  3. Enter the email from `ALERT_EMAIL_TO`

### SMS (Primary -- Active Now)

- **Telnyx** sends CRITICAL alerts (daily loss limit hit, crash, deployment failure)
- Configured via `TELNYX_API_KEY`, `TELNYX_FROM_NUMBER`, `ALERT_SMS_TO` env vars
- SMS is reserved for events requiring immediate human attention

### UptimeRobot SMS (Optional)

- UptimeRobot Pro ($7/month) includes SMS alerts
- Configure as backup alert channel if Telnyx has issues

---

## Monitoring Intervals

| Monitor | Interval | Rationale |
|---------|----------|-----------|
| Health endpoint (normal) | 5 minutes | Sufficient for steady-state operation |
| Health endpoint (critical) | 1 minute | Post-deploy or first 2 weeks live |
| Sentry error tracking | Real-time | Errors captured as they occur |
| Daily performance email | Once daily at 18:00 EST | End-of-day summary |
| Railway resource usage | Manual daily check | Part of 5-minute daily runbook |

---

## Dashboard Metrics to Watch

### Daily Runbook (5 minutes)

1. **UptimeRobot Dashboard**
   - Uptime % (target: 99.9%)
   - Response time trend (target p95: < 500ms)
   - Any downtime incidents in last 24 hours

2. **Sentry Dashboard**
   - New unresolved errors (target: 0)
   - Error frequency trend
   - Any errors with `level: critical`

3. **Daily Performance Email**
   - Trades executed today
   - Win rate (rolling 50-trade)
   - Daily P&L
   - System health summary

4. **Railway Dashboard**
   - Memory usage (watch for unbounded growth)
   - CPU usage (should be low during non-market hours)
   - Deploy history (any failed deploys)

### Weekly Review

- UptimeRobot weekly report: uptime %, average response time
- Sentry weekly digest: error trends, resolved vs new
- Railway billing: stay within $17-60/month budget

---

## Incident Response

### Health Endpoint Down (UptimeRobot alert)

1. Check Railway logs: `railway logs --tail 100`
2. Check if supervisord is running both processes
3. If health server up but engine down: supervisord will auto-restart (check `startretries`)
4. If both down: check Railway deployment status, redeploy if needed
5. If persistent: check Supabase and OANDA status pages for upstream outages

### Error Spike (Sentry alert)

1. Check Sentry for the specific error type and stack trace
2. If broker-related: check OANDA status, circuit breaker may have tripped
3. If database-related: check Supabase status page
4. If deployment-related: rollback via `railway rollback`

### SMS Alert Received (Critical)

1. This means daily loss limit, crash, or deployment failure
2. Immediately check the dashboard kill switch
3. If in doubt, activate kill switch first, investigate second
4. Check Railway logs and Sentry for details
