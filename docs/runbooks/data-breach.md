# Runbook: Data Breach

**Severity:** P1 (always)
**Owner:** Security On-Call + Legal/Compliance
**Last Updated:** 2026-03-26

---

## IMPORTANT: Legal Hold

The moment a data breach is suspected, initiate a **legal hold** on all relevant logs, backups, and system state. Do not delete, rotate, or overwrite any evidence until cleared by legal counsel.

---

## 1. Immediate Containment (first 15 minutes)

### 1a. Disable compromised access

```bash
# Revoke ALL API keys for affected accounts
# Via database:
```

```sql
-- Disable all keys for a compromised owner
UPDATE api_keys SET is_active = false WHERE owner = '<compromised_owner>';

-- Nuclear option: disable ALL keys if scope is unknown
UPDATE api_keys SET is_active = false;
```

### 1b. Rotate secrets

```bash
# 1. Generate new JWT secret
python -c "import secrets; print(secrets.token_hex(32))"

# 2. Update .env with new values
#    BITMOD_JWT_SECRET=<new_secret>
#    BITMOD_API_KEYS=<new_keys>

# 3. Restart all services to pick up new secrets
docker compose down
docker compose up -d

# 4. Rotate database credentials
#    Update POSTGRES_PASSWORD in .env
#    Update password in PostgreSQL:
docker exec bitmod-postgres psql -U postgres -c \
  "ALTER USER bitmod PASSWORD '<new_password>';"
```

### 1c. Isolate affected systems

```bash
# If running in Docker, disconnect from external network
docker network disconnect bitmod-public bitmod-gateway

# If running in Kubernetes, apply a deny-all network policy
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: emergency-deny-all
spec:
  podSelector:
    matchLabels:
      app: bitmod
  policyTypes:
  - Ingress
  - Egress
EOF
```

### 1d. Preserve running state before changes

```bash
# Capture container state
docker inspect bitmod-gateway > /tmp/evidence/gateway-inspect.json
docker inspect bitmod-chat > /tmp/evidence/chat-inspect.json

# Capture running processes
docker exec bitmod-gateway ps aux > /tmp/evidence/gateway-processes.txt
docker exec bitmod-chat ps aux > /tmp/evidence/chat-processes.txt

# Capture network connections
docker exec bitmod-gateway ss -tunapl > /tmp/evidence/gateway-connections.txt
```

---

## 2. Evidence Preservation

### 2a. Snapshot databases

```bash
# Create evidence directory with timestamp
EVIDENCE_DIR="/tmp/evidence/breach-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$EVIDENCE_DIR"

# PostgreSQL: full dump
docker exec bitmod-postgres pg_dump -U bitmod bitmod \
  > "$EVIDENCE_DIR/postgres-full-dump.sql"

# SQLite: copy the database file
cp /path/to/bitmod.db "$EVIDENCE_DIR/bitmod.db.snapshot"

# Export audit events specifically
docker exec bitmod-postgres psql -U bitmod -c \
  "COPY audit_events TO STDOUT WITH CSV HEADER;" \
  > "$EVIDENCE_DIR/audit_events.csv"
```

### 2b. Capture logs

```bash
# Export all container logs
docker logs bitmod-gateway --timestamps > "$EVIDENCE_DIR/gateway.log" 2>&1
docker logs bitmod-chat --timestamps > "$EVIDENCE_DIR/chat.log" 2>&1
docker logs bitmod-postgres --timestamps > "$EVIDENCE_DIR/postgres.log" 2>&1

# If using centralized logging (Loki, etc.), export the time window
# covering the breach period

# Capture Docker events
docker events --since "24h" --until "now" > "$EVIDENCE_DIR/docker-events.log"
```

### 2c. Capture network evidence

```bash
# DNS queries (if logging is enabled)
# Firewall logs
# Load balancer access logs
# WAF logs (if applicable)
```

### 2d. Hash all evidence files

```bash
# Create integrity hashes for all collected evidence
cd "$EVIDENCE_DIR"
sha256sum * > evidence-checksums.sha256
```

---

## 3. Investigation

### 3a. Build timeline

```sql
-- All audit events in the breach window, ordered chronologically
SELECT timestamp, event_type, actor, source_ip, action, outcome, details_json
FROM audit_events
WHERE timestamp BETWEEN '<breach_start>' AND '<breach_end>'
ORDER BY timestamp ASC;
```

### 3b. Identify what data was accessed

```sql
-- Cache queries made during breach window (may contain exfiltrated data)
SELECT id, query_hash, created_at, hit_count
FROM answer_cache
WHERE created_at BETWEEN '<breach_start>' AND '<breach_end>'
ORDER BY created_at ASC;

-- Check for bulk data access patterns
SELECT actor, COUNT(*) as request_count,
       MIN(timestamp) as first_request,
       MAX(timestamp) as last_request
FROM audit_events
WHERE timestamp BETWEEN '<breach_start>' AND '<breach_end>'
  AND outcome = 'success'
GROUP BY actor
ORDER BY request_count DESC;
```

### 3c. Identify affected users

```sql
-- Users whose data may have been accessed
-- Cross-reference with the queries made during the breach
SELECT DISTINCT actor, source_ip
FROM audit_events
WHERE timestamp BETWEEN '<breach_start>' AND '<breach_end>'
ORDER BY actor;

-- API keys used during breach
SELECT ak.id, ak.name, ak.owner, ak.key_preview, ak.created_at
FROM api_keys ak
WHERE ak.last_used_at BETWEEN '<breach_start>' AND '<breach_end>';
```

### 3d. Determine attack vector

Check each possible entry point:

1. **Compromised API key** -- see `api-key-compromise.md`
2. **Exploited vulnerability** -- check for unusual request patterns in gateway logs
3. **Insider threat** -- check for authorized-but-abnormal access patterns
4. **Supply chain** -- see `dependency-compromise.md`
5. **Infrastructure** -- check cloud provider audit logs for unauthorized access

---

## 4. Notification Obligations

### 4a. Timeline requirements

| Jurisdiction | Notification Deadline | Authority |
|-------------|----------------------|-----------|
| GDPR (EU/EEA) | 72 hours from awareness | Supervisory Authority |
| CCPA (California) | "Expedient" / "without unreasonable delay" | CA Attorney General (>500 residents) |
| HIPAA (US health data) | 60 days | HHS OCR |
| State breach laws (US) | Varies by state (30-90 days) | State AG |

### 4b. Who to notify

1. **Internal stakeholders** (immediate):
   - Engineering leadership
   - Security team
   - Legal/compliance
   - Executive team

2. **Regulatory bodies** (per timeline above):
   - Data protection authority (GDPR)
   - State attorney general (US state laws)
   - Sector-specific regulators (HIPAA, PCI, etc.)

3. **Affected individuals** (after regulatory filing):
   - Users whose personal data was accessed
   - Customers whose API keys were compromised
   - Partners whose data was in the affected systems

4. **Law enforcement** (if criminal activity suspected):
   - FBI IC3 (cyber crime)
   - Local law enforcement

### 4c. Notification content

Each notification must include:

- Nature of the breach (what happened)
- Categories of data affected
- Approximate number of affected individuals
- Likely consequences
- Measures taken to address the breach
- Contact point for further information
- Recommendations for affected individuals (password changes, monitoring, etc.)

---

## 5. Remediation

### 5a. Fix the vulnerability

Based on investigation findings, apply the appropriate fix:

- Patch the exploited vulnerability
- Harden configurations
- Update access controls
- Strengthen input validation

### 5b. Verify fix effectiveness

```bash
# Run security test suite
python -m pytest tests/test_security.py tests/test_security_expanded.py -v

# Run auth test suite
python -m pytest tests/test_auth.py -v
```

### 5c. Restore service

```bash
# Reconnect to network (if isolated)
docker network connect bitmod-public bitmod-gateway

# Issue new API keys to affected users
# See api-key-compromise.md for procedure

# Verify service health
curl -s http://localhost:8000/health
```

### 5d. Enhanced monitoring

After restoration, increase monitoring sensitivity:

- Lower alert thresholds for auth failures
- Enable verbose logging for 7 days
- Set up canary tokens in sensitive data stores
- Review access logs daily for the next 30 days

---

## 6. Post-Breach Checklist

- [ ] Evidence preserved and hashed (chain of custody documented)
- [ ] Timeline of breach reconstructed
- [ ] Root cause identified
- [ ] All affected data catalogued
- [ ] All affected users identified
- [ ] Regulatory notifications filed within required timelines
- [ ] Affected individuals notified
- [ ] Vulnerability patched and verified
- [ ] All credentials rotated (API keys, JWT secrets, DB passwords)
- [ ] Enhanced monitoring in place
- [ ] Post-mortem conducted (see `service-outage.md` for template)
- [ ] Lessons learned documented and shared
- [ ] Insurance carrier notified (if applicable)
- [ ] Legal counsel engaged for ongoing obligations
