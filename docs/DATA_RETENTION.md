# Data Retention Policy

**Effective Date:** 2026-03-26
**Owner:** Security & Compliance
**Review Frequency:** Annually

---

## Overview

This document defines data retention periods for all data categories within Bitmod deployments. Operators deploying Bitmod are responsible for configuring these policies to meet their own regulatory and compliance requirements. The defaults below represent recommended baselines.

---

## Retention Schedule

| Data Category | Retention Period | Storage Location | Deletion Method |
|--------------|-----------------|------------------|-----------------|
| Application logs | 90 days | Container stdout / log aggregator | Automatic rotation |
| Security / audit logs (`audit_events`) | 1 year (365 days) | Database (`audit_events` table) | Scheduled purge job |
| Cache entries (`answer_cache`) | Configurable TTL (default: 30 days) | Database (`answer_cache` table) | TTL expiration + LRU eviction |
| Conversation history | 90 days | Database (chat session tables) | Scheduled purge job |
| Backup journals | 90 days | Filesystem (`bitmod_backup/` directory) | Scheduled cleanup script |
| User data (API keys, profiles) | Per compliance requirements | Database (`api_keys` table) | Manual or on account deletion |
| Rate limiter state | Ephemeral (window-based) | Redis / in-memory | Automatic expiration |
| Prometheus metrics | 15 days (default) | Prometheus TSDB | Automatic compaction |
| Embedding vectors | Same as parent cache entry | Database / vector store | Cascade delete with cache entry |

---

## Detailed Policies

### Application Logs (90 days)

Application logs include request/response metadata, error traces, and operational events from the gateway and chat services.

**Configuration:**

```yaml
# Docker Compose log rotation
services:
  gateway:
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "10"
```

```bash
# For centralized logging (Loki, CloudWatch, etc.), set retention:
# Loki: -table-manager.retention-period=2160h  (90 days)
# CloudWatch: retention policy = 90 days
# Elasticsearch: ILM policy with delete phase at 90 days
```

**What is logged:** Request method, path, status code, latency, correlation ID, client IP (hashed), error messages. Raw request/response bodies are NOT logged.

**What is NOT logged:** API keys (masked via `mask_sensitive_value()`), JWT tokens, user query content, LLM responses.

### Security / Audit Logs (1 year)

Audit events in the `audit_events` table record authentication, authorization, key management, and security events. These are retained longer for forensic investigation and compliance.

**Purge procedure:**

```sql
-- Run monthly: delete audit events older than 1 year
DELETE FROM audit_events
WHERE timestamp < datetime('now', '-365 days');

-- PostgreSQL variant:
DELETE FROM audit_events
WHERE timestamp::timestamptz < NOW() - INTERVAL '365 days';
```

**Recommended automation:**

```bash
# Add to crontab or Kubernetes CronJob
# Monthly audit log cleanup (1st of each month at 3 AM UTC)
0 3 1 * * sqlite3 /app/data/bitmod.db "DELETE FROM audit_events WHERE timestamp < datetime('now', '-365 days');"
```

**Before deletion:** Export to immutable long-term storage (S3 Glacier, Azure Archive) if regulatory requirements exceed 1 year.

### Cache Entries (configurable TTL, default 30 days)

Cache entries in `answer_cache` are governed by TTL-based expiration and LRU eviction. The cache engine handles this automatically.

**Configuration:**

```bash
# Environment variable
BITMOD_CACHE_TTL_DAYS=30

# Or in bitmod.yaml
cache:
  ttl_days: 30
  max_entries: 100000
  eviction_policy: lru
```

**Manual cleanup:**

```sql
-- Remove expired cache entries
DELETE FROM answer_cache
WHERE created_at < datetime('now', '-30 days');

-- Remove entries exceeding max count (keep most recently hit)
DELETE FROM answer_cache
WHERE id NOT IN (
  SELECT id FROM answer_cache
  ORDER BY last_hit_at DESC
  LIMIT 100000
);
```

### Conversation History (90 days)

Chat session data including queries, responses, and session metadata.

**Purge procedure:**

```sql
-- Delete conversation sessions older than 90 days
DELETE FROM chat_sessions
WHERE created_at < datetime('now', '-90 days');

-- Delete orphaned messages
DELETE FROM chat_messages
WHERE session_id NOT IN (SELECT id FROM chat_sessions);
```

### Backup Journals (90 days)

The `BackupManager` stores append-only JSONL journals in the `bitmod_backup/` directory.

**Cleanup procedure:**

```bash
# Delete backup journals older than 90 days
find /app/data/bitmod_backup -name "*.jsonl" -mtime +90 -delete
find /app/data/bitmod_backup -name "*.jsonl.gz" -mtime +90 -delete

# Verify remaining backups
ls -la /app/data/bitmod_backup/
```

### User Data (per compliance requirements)

API keys, user profiles, and account data are retained as long as the account is active. Retention after account deletion depends on the operator's compliance requirements.

**On account deletion:**

```sql
-- Deactivate all API keys for the user
UPDATE api_keys SET is_active = false WHERE owner = '<user_id>';

-- After grace period (30 days), hard delete
DELETE FROM api_keys WHERE owner = '<user_id>' AND is_active = false;
```

---

## GDPR Right to Erasure Process

When a data subject exercises their right to erasure under GDPR Article 17, the following process applies.

### Step 1: Verify the request

- Confirm the identity of the requester (proof of account ownership)
- Confirm the request is valid (no legal obligation to retain the data)
- Acknowledge receipt within 72 hours

### Step 2: Identify all personal data

Personal data may exist in the following locations:

| Location | Data Type | Identifier |
|----------|-----------|------------|
| `api_keys` table | Key name, owner, email, key preview | `owner` field, `email` field |
| `audit_events` table | Actor, source IP, actions | `actor` field, `source_ip` field |
| `answer_cache` table | Cached queries (may contain PII in questions) | Search `query` content |
| Backup journals | Historical queries and responses | Search JSONL files |
| Application logs | IP addresses, correlation IDs | Search log files |

### Step 3: Execute erasure

```sql
-- 1. Delete API keys
DELETE FROM api_keys WHERE owner = '<user_id>' OR email = '<user_email>';

-- 2. Anonymize audit events (retain for security, remove PII)
UPDATE audit_events
SET actor = 'REDACTED',
    source_ip = 'REDACTED',
    details_json = NULL
WHERE actor = '<user_id>'
   OR source_ip = '<user_ip>';

-- 3. Delete cache entries containing user's queries
DELETE FROM answer_cache
WHERE id IN (
  SELECT id FROM answer_cache
  WHERE query LIKE '%<user_identifier>%'
);

-- 4. Delete from backup journals
-- Search and redact JSONL files:
```

```bash
# Search backup journals for user data
grep -rl '<user_identifier>' /app/data/bitmod_backup/

# Redact user data from journals (create redacted copy, replace original)
for f in $(grep -rl '<user_identifier>' /app/data/bitmod_backup/); do
  sed 's/<user_identifier>/REDACTED/g' "$f" > "$f.redacted"
  mv "$f.redacted" "$f"
done
```

### Step 4: Confirm and respond

- Verify all data stores have been processed
- Document the erasure actions taken
- Respond to the data subject within 30 days of the original request
- Record the erasure request in an internal register (without PII)

### Step 5: Exceptions

Data may be retained despite an erasure request if:

- Required for compliance with a legal obligation
- Required for the establishment, exercise, or defense of legal claims
- Required for archiving in the public interest
- Part of an active security investigation (retain until investigation concludes, then erase)

---

## Implementation Notes

### Automated retention enforcement

Operators should configure a scheduled job (cron, Kubernetes CronJob, or cloud scheduler) to enforce retention periods automatically:

```bash
#!/usr/bin/env bash
# retention-cleanup.sh -- run daily via cron
set -euo pipefail

DB_PATH="${BITMOD_DB_PATH:-/app/data/bitmod.db}"

echo "[$(date -u)] Starting retention cleanup"

# Audit events: 1 year
sqlite3 "$DB_PATH" "DELETE FROM audit_events WHERE timestamp < datetime('now', '-365 days');"
echo "  Audit events pruned"

# Cache entries: 30 days (or configured TTL)
sqlite3 "$DB_PATH" "DELETE FROM answer_cache WHERE created_at < datetime('now', '-30 days');"
echo "  Cache entries pruned"

# Conversation history: 90 days
sqlite3 "$DB_PATH" "DELETE FROM chat_sessions WHERE created_at < datetime('now', '-90 days');"
echo "  Chat sessions pruned"

# Backup journals: 90 days
find /app/data/bitmod_backup -name "*.jsonl*" -mtime +90 -delete 2>/dev/null || true
echo "  Backup journals pruned"

echo "[$(date -u)] Retention cleanup complete"
```

### Monitoring retention compliance

- Alert if `audit_events` table contains records older than 365 days
- Alert if `answer_cache` table size exceeds `max_entries` threshold
- Alert if backup directory exceeds configured disk quota
- Include retention compliance in quarterly security reviews
