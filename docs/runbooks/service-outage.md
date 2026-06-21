# Runbook: Service Outage

**Severity:** P1 (full outage) / P2 (partial degradation)
**Owner:** Engineering On-Call
**Last Updated:** 2026-03-26

---

## 1. Triage (first 5 minutes)

### 1a. Identify which service is down

```bash
# Check all container status
docker compose ps

# Quick health check on each service
curl -s http://localhost:8000/health   # Gateway
curl -s http://localhost:8001/health   # Chat service

# Check if frontend is responding (if deployed)
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
```

### 1b. Check container logs for crash reason

```bash
# Gateway logs (last 100 lines)
docker logs bitmod-gateway --tail 100

# Chat service logs
docker logs bitmod-chat --tail 100

# Look for OOM kills
docker inspect bitmod-gateway | grep -A5 "State"
docker inspect bitmod-chat | grep -A5 "State"

# System-level: check if Docker daemon itself is healthy
docker info
```

### 1c. Check resource exhaustion

```bash
# Disk space
df -h

# Memory
free -m

# CPU load
uptime

# Docker resource usage
docker stats --no-stream
```

### 1d. Check external dependencies

```bash
# Database connectivity (PostgreSQL)
docker exec bitmod-postgres pg_isready

# Redis connectivity
docker exec bitmod-redis redis-cli ping

# Upstream LLM provider reachability
curl -s -o /dev/null -w "%{http_code}" https://api.openai.com/v1/models
curl -s -o /dev/null -w "%{http_code}" https://api.anthropic.com/v1/messages
```

---

## 2. Escalation Criteria

| Condition | Action |
|-----------|--------|
| Single service restart fixes it | P3 -- monitor, no escalation needed |
| Service keeps crashing after restart | P2 -- investigate root cause, notify team lead |
| Database is down or corrupted | P1 -- escalate to database owner immediately |
| Multiple services down simultaneously | P1 -- likely infrastructure issue, escalate to platform team |
| Data loss suspected | P1 -- invoke data breach runbook, escalate to security |
| Customer-reported outage lasting > 15 min | P1 -- activate incident commander, update status page |

---

## 3. Recovery Procedures

### 3a. Restart the failed service

```bash
# Restart a single service
docker compose restart gateway

# If restart doesn't help, recreate the container
docker compose up -d --force-recreate gateway

# If the image might be corrupted, rebuild
docker compose build --no-cache gateway
docker compose up -d gateway
```

### 3b. Rollback deployment

```bash
# Check recent deployments
git log --oneline -10

# Rollback to last known-good commit
git checkout <commit_hash>

# Rebuild and deploy
docker compose build gateway chat
docker compose up -d gateway chat
```

### 3c. Database recovery

```bash
# PostgreSQL: check if database is accepting connections
docker exec bitmod-postgres psql -U bitmod -c "SELECT 1;"

# PostgreSQL: restart if unresponsive
docker compose restart postgres

# SQLite: check database integrity
sqlite3 /path/to/bitmod.db "PRAGMA integrity_check;"

# SQLite: restore from backup if corrupted
cp /path/to/backup/bitmod.db /path/to/bitmod.db
docker compose restart gateway chat
```

### 3d. Redis recovery

```bash
# Check Redis health
docker exec bitmod-redis redis-cli info server

# Flush Redis if cache corruption suspected (rate limiter will rebuild)
docker exec bitmod-redis redis-cli FLUSHDB

# Restart Redis
docker compose restart redis
```

### 3e. Full stack restart

```bash
# Nuclear option: restart everything
docker compose down
docker compose up -d

# Verify all services are healthy
docker compose ps
curl -s http://localhost:8000/health | python -m json.tool
```

---

## 4. Communication Template

### Status Page Update (during outage)

```
Title: [Service Degradation/Outage] Bitmod API

Status: Investigating / Identified / Monitoring / Resolved

Body:
We are currently experiencing [degraded performance / an outage] affecting
[the Bitmod API / cache lookups / chat service]. Our team is actively
investigating.

Impact: [Describe what users are experiencing -- failed requests, slow
responses, etc.]

Timeline:
- HH:MM UTC -- Issue first detected via [monitoring alert / customer report]
- HH:MM UTC -- Engineering on-call engaged
- HH:MM UTC -- Root cause identified: [brief description]
- HH:MM UTC -- Fix deployed, monitoring for recovery

Next update in 30 minutes or when status changes.
```

### Status Page Update (resolved)

```
Title: [Resolved] Bitmod API [Service Degradation/Outage]

Status: Resolved

Body:
The [degraded performance / outage] affecting [component] has been resolved.
The root cause was [brief description]. A full post-mortem will be published
within 48 hours.

Duration: HH:MM UTC to HH:MM UTC (X hours Y minutes)

Impact: [Number of affected requests / users / error rate during window]
```

---

## 5. Post-Mortem Template

```markdown
# Post-Mortem: [Incident Title]

**Date:** YYYY-MM-DD
**Duration:** HH:MM to HH:MM UTC (X hours Y minutes)
**Severity:** P1 / P2 / P3
**Author:** [Name]

## Summary
One-paragraph description of what happened and the user impact.

## Timeline (all times UTC)
| Time | Event |
|------|-------|
| HH:MM | First alert / detection |
| HH:MM | On-call engaged |
| HH:MM | Root cause identified |
| HH:MM | Fix applied |
| HH:MM | Service restored |
| HH:MM | Monitoring confirmed stable |

## Root Cause
What broke and why.

## Impact
- Requests affected: N
- Users affected: N
- Error rate during incident: X%
- Revenue impact (if applicable): $X

## Detection
How was the incident detected? (Alert, customer report, manual check)
Gap: Could we have detected it sooner?

## Resolution
What was done to fix the immediate issue?

## Action Items
| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| [Preventive measure] | [Name] | YYYY-MM-DD | Open |
| [Detection improvement] | [Name] | YYYY-MM-DD | Open |
| [Process improvement] | [Name] | YYYY-MM-DD | Open |

## Lessons Learned
- What went well?
- What could have gone better?
- Where did we get lucky?
```

---

## 6. Health Check Reference

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| Gateway | `GET /health` | `200 {"status": "ok"}` |
| Chat | `GET /health` | `200 {"status": "ok"}` |
| PostgreSQL | `pg_isready` | Exit code 0 |
| Redis | `redis-cli ping` | `PONG` |
| Frontend | `GET /` | `200` |
