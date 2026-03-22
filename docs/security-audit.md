# Lumitrade Pre-Launch Security Audit

Complete every item before depositing any real capital. This is the minimum security bar for a live trading system.

Source: SS v2.0 Section 9.1

---

## Secrets (6 items)

| # | Audit Item | How to Verify | Status |
|---|-----------|---------------|--------|
| S-01 | gitleaks full history scan returns zero findings | Run: `gitleaks detect --source . --log-opts="--all"` | [ ] |
| S-02 | GitHub secret scanning enabled on repository | GitHub repo Settings > Code security and analysis > Secret scanning: Enabled | [ ] |
| S-03 | pre-commit hook installed and tested (commit a fake key -- should be blocked) | Stage a file containing `sk-ant-api03-FAKE`, run `git commit` -- hook must reject | [ ] |
| S-04 | All .env files confirmed in .gitignore | Run: `grep "\.env" .gitignore` -- confirm `.env`, `.env.local`, `.env.production` listed | [ ] |
| S-05 | No secrets in any GitHub Actions workflow files (use `${{ secrets.X }}`) | Review all `.github/workflows/*.yml` -- no hardcoded keys, all use `${{ secrets.X }}` syntax | [ ] |
| S-06 | All 6 API keys confirmed as Railway env vars (not in code) | Check Railway dashboard for: OANDA_API_KEY_DATA, OANDA_API_KEY_TRADE, ANTHROPIC_API_KEY, SUPABASE_SERVICE_KEY, TWILIO_AUTH_TOKEN, SENDGRID_API_KEY | [ ] |

## OANDA (4 items)

| # | Audit Item | How to Verify | Status |
|---|-----------|---------------|--------|
| O-01 | Read-only key assigned to data engine only (confirmed in code) | Grep codebase: only `data_engine/` references `OANDA_API_KEY_DATA` | [ ] |
| O-02 | Trading key assigned to execution engine only (confirmed in code) | Grep codebase: only `execution_engine/` references `OANDA_API_KEY_TRADE` | [ ] |
| O-03 | IP whitelist active -- test from non-whitelisted IP confirms rejection | Make API call from a different IP/network -- confirm 403 or connection refused | [ ] |
| O-04 | 2FA enabled on OANDA web portal account | Log into OANDA portal -- confirm 2FA prompt appears | [ ] |

## TLS (2 items)

| # | Audit Item | How to Verify | Status |
|---|-----------|---------------|--------|
| T-01 | TLS 1.3 confirmed on all OANDA API calls | Run: `curl -v https://api-fxpractice.oanda.com/v3/accounts` -- verify TLS 1.3 in handshake | [ ] |
| T-02 | No `verify=False` anywhere in codebase | Run: `grep -r "verify=False" --include="*.py"` -- zero results | [ ] |

## Logging (3 items)

| # | Audit Item | How to Verify | Status |
|---|-----------|---------------|--------|
| L-01 | Test log with embedded API key -- confirm scrubbed in Railway logs | Log a message containing an API key pattern, check Railway logs -- key must be redacted | [ ] |
| L-02 | Test log with email address -- confirm scrubbed | Log a message containing `user@example.com`, check output -- email must be redacted | [ ] |
| L-03 | Sentry before_send scrubber confirmed working (test error sent) | Trigger a test error with sensitive data, check Sentry dashboard -- data must be scrubbed | [ ] |

## Database (3 items)

| # | Audit Item | How to Verify | Status |
|---|-----------|---------------|--------|
| D-01 | Supabase RLS confirmed active on all 7 tables | Supabase dashboard > each table > RLS toggle is ON | [ ] |
| D-02 | Anon key confirmed cannot read data without auth | Use anon key to query tables without JWT -- should return empty or 403 | [ ] |
| D-03 | Service key confirmed NOT in any frontend code or env vars | Grep `frontend/` for `service_role` or `SUPABASE_SERVICE_KEY` -- zero results | [ ] |

## Frontend (4 items)

| # | Audit Item | How to Verify | Status |
|---|-----------|---------------|--------|
| F-01 | Security headers confirmed via securityheaders.com scan | Submit dashboard URL to securityheaders.com -- expect A or A+ grade | [ ] |
| F-02 | CSP blocks loading from unauthorized domains (test with devtools) | Open devtools Console, attempt to load script from unauthorized domain -- should be blocked | [ ] |
| F-03 | Dashboard login page tested -- invalid credentials rejected | Submit wrong email/password -- confirm error message, no access granted | [ ] |
| F-04 | API routes tested without auth -- confirm 401 returned | Call `/api/signals`, `/api/trades` without auth header -- all return 401 | [ ] |

## Dependencies (3 items)

| # | Audit Item | How to Verify | Status |
|---|-----------|---------------|--------|
| P-01 | npm audit returns zero high/critical vulnerabilities | Run: `cd frontend && npm audit` -- zero high/critical | [ ] |
| P-02 | pip-audit returns zero known vulnerabilities | Run: `pip-audit -r requirements.txt` -- zero known vulnerabilities | [ ] |
| P-03 | All Python deps have hash verification (requirements.txt) | Inspect `requirements.txt` -- each dependency has `--hash=sha256:...` | [ ] |

## Docker (1 item)

| # | Audit Item | How to Verify | Status |
|---|-----------|---------------|--------|
| K-01 | Container runs as non-root user | Run: `docker exec <container> whoami` -- output must be `lumitrade`, not `root` | [ ] |

## Kill Switch (1 item)

| # | Audit Item | How to Verify | Status |
|---|-----------|---------------|--------|
| W-01 | Kill switch requires typed confirmation -- tested that single click does nothing | Click kill switch button once -- confirm modal appears requiring typed confirmation before action executes | [ ] |

---

## Summary

| Category | Items | Checked |
|----------|-------|---------|
| Secrets | 6 | _ / 6 |
| OANDA | 4 | _ / 4 |
| TLS | 2 | _ / 2 |
| Logging | 3 | _ / 3 |
| Database | 3 | _ / 3 |
| Frontend | 4 | _ / 4 |
| Dependencies | 3 | _ / 3 |
| Docker | 1 | _ / 1 |
| Kill Switch | 1 | _ / 1 |
| **Total** | **27** | **_ / 27** |

**All 27 items must be checked before Go/No-Go Gate G-009 can be marked as verified.**
