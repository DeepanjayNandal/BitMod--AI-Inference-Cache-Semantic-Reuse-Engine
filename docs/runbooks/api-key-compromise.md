# Runbook: API Key Compromise

**Severity:** P1 (if admin-scoped key) / P2 (if read/write-scoped key)
**Owner:** Security On-Call
**Last Updated:** 2026-03-26

---

## 1. Detection Indicators

Signs that an API key may be compromised:

- Sudden spike in requests from a single key (check rate limiter logs for `rate_limited` events)
- Requests originating from unexpected IP addresses or geolocations
- Auth failures followed by auth successes on the same key (credential stuffing pattern)
- Usage of a key outside normal business hours
- A key accessing resources outside its normal scope
- Customer reports unauthorized usage on their account
- Audit events showing `auth_failure` followed by `auth_success` for the same actor

**Where to look:**

```sql
-- Recent auth events for a suspect key (audit_events table)
SELECT timestamp, event_type, actor, source_ip, action, outcome, details_json
FROM audit_events
WHERE actor LIKE '%<key_hash_prefix>%'
  OR details_json LIKE '%<key_hash_prefix>%'
ORDER BY timestamp DESC
LIMIT 100;

-- Auth failures in the last 24 hours
SELECT timestamp, actor, source_ip, outcome
FROM audit_events
WHERE event_type = 'auth_failure'
  AND timestamp > datetime('now', '-24 hours')
ORDER BY timestamp DESC;
```

**Application logs:**

```bash
# Search gateway logs for the compromised key's hash prefix
docker logs bitmod-gateway 2>&1 | grep "auth_failure"
docker logs bitmod-gateway 2>&1 | grep "<key_hash_prefix>"

# Check security event log
docker logs bitmod-gateway 2>&1 | grep "security_event"
```

---

## 2. Immediate Containment

**Goal:** Revoke the compromised key within 5 minutes of confirmation.

### 2a. Revoke via API (preferred)

```bash
# If you have admin API access, revoke the key by ID
curl -X POST https://<gateway>/v1/admin/keys/<key_id>/revoke \
  -H "Authorization: ApiKey <admin_key>"
```

### 2b. Revoke via database (direct)

```sql
-- SQLite (development)
UPDATE api_keys SET is_active = 0 WHERE id = '<key_id>';

-- PostgreSQL (production)
UPDATE api_keys SET is_active = false WHERE id = '<key_id>';
```

### 2c. Revoke via environment variable removal

If the key was configured via `BITMOD_API_KEYS` env var:

```bash
# 1. Remove the compromised key from BITMOD_API_KEYS in .env
#    Format: BITMOD_API_KEYS=key1:read,key2:read:write
#    Remove the compromised entry

# 2. Restart the gateway to pick up the change
docker compose up -d gateway
```

### 2d. Emergency: block at network level

If the attacker IP is known:

```bash
# Block IP at firewall (Linux)
sudo iptables -A INPUT -s <attacker_ip> -j DROP

# Or via cloud provider security group / WAF rule
```

---

## 3. Investigation

### 3a. Determine scope of compromise

```sql
-- What did the compromised key access?
SELECT timestamp, action, resource, outcome, source_ip, details_json
FROM audit_events
WHERE actor LIKE '%<key_identifier>%'
ORDER BY timestamp ASC;

-- Were any write operations performed?
SELECT * FROM audit_events
WHERE actor LIKE '%<key_identifier>%'
  AND action IN ('create', 'update', 'delete', 'ingest', 'write')
ORDER BY timestamp ASC;
```

### 3b. Check for data exfiltration

```sql
-- High-volume read patterns (potential bulk extraction)
SELECT DATE(timestamp) as day, COUNT(*) as request_count
FROM audit_events
WHERE actor LIKE '%<key_identifier>%'
  AND outcome = 'success'
GROUP BY DATE(timestamp)
ORDER BY day DESC;
```

### 3c. Identify the leak vector

- Was the key committed to a public repository? (`git log --all -p | grep "<key_prefix>"`)
- Was it exposed in client-side code or browser network tab?
- Was it shared in an insecure channel (email, Slack, etc.)?
- Was the key owner's machine compromised?
- Was it leaked via an application log? (`grep -r "<key_prefix>" /var/log/`)

### 3d. Check for lateral movement

```sql
-- Did the attacker create new keys?
SELECT * FROM audit_events
WHERE event_type = 'key_created'
  AND timestamp > '<compromise_start_time>'
ORDER BY timestamp ASC;

-- Any scope escalation attempts?
SELECT * FROM audit_events
WHERE action LIKE '%scope%' OR action LIKE '%permission%'
  AND timestamp > '<compromise_start_time>';
```

---

## 4. Recovery

### 4a. Issue replacement key

```bash
# Generate a new key for the affected user/service
curl -X POST https://<gateway>/v1/admin/keys \
  -H "Authorization: ApiKey <admin_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "<descriptive_name>",
    "scopes": ["read", "write"],
    "owner": "<owner_id>"
  }'
```

Or programmatically:

```python
from bitmod.auth import APIKeyManager

mgr = APIKeyManager(db_backend)
raw_key, record = mgr.create_key(
    name="replacement-key-for-<service>",
    owner="<owner>",
    scopes=["read", "write"],
    expires_in_days=90,
)
# Securely deliver raw_key to the key owner
print(f"New key: {raw_key}")
print(f"Key ID: {record.id}")
```

### 4b. Notify affected users

Send notification to the key owner with:

- Confirmation that the old key has been revoked
- The new key (via secure channel only -- never email plaintext keys)
- Summary of what was accessed during the compromise window
- Recommended actions (rotate any downstream credentials the key could access)

### 4c. Update dependent services

If the compromised key was used by internal services:

1. Update the key in the service's environment/secrets manager
2. Restart the service: `docker compose restart <service>`
3. Verify the service is healthy: `curl http://<service>:8000/health`

---

## 5. Post-Incident Review Checklist

- [ ] Timeline documented: when was the key compromised, when was it detected, when was it revoked?
- [ ] Leak vector identified and remediated
- [ ] All data accessed by the compromised key catalogued
- [ ] Replacement keys issued and distributed securely
- [ ] Dependent services updated and verified healthy
- [ ] Audit log preserved for the compromise window (export to immutable storage)
- [ ] Detection gap assessed: could we have caught this sooner?
- [ ] Key rotation policy reviewed (consider mandatory expiration via `expires_in_days`)
- [ ] Monitoring improved: add alerts for the specific pattern that indicated compromise
- [ ] Incident report written and shared with stakeholders
- [ ] If customer data was accessed: legal/compliance team notified per data breach runbook

---

## 6. Prevention Measures

- Set key expiration: use `expires_in_days` when creating keys
- Enforce least-privilege scopes: use `read` only unless `write` or `admin` is needed
- Monitor `auth_failure` audit events with alerting thresholds
- Never log raw API keys -- use `mask_sensitive_value()` from `bitmod.security`
- Store keys in secrets managers, never in source code or environment files committed to git
- Rotate keys on a regular schedule (90 days recommended)
