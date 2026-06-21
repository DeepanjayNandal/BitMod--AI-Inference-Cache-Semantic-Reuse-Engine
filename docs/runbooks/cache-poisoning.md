# Runbook: Cache Poisoning

**Severity:** P1 (if serving malicious content) / P2 (if serving stale/incorrect data)
**Owner:** Security On-Call
**Last Updated:** 2026-03-26

---

## 1. Detection

Cache poisoning occurs when an attacker manipulates inputs to store malicious or incorrect content in the cache, which is then served to other users. In Bitmod, the 9-layer cache engine uses composite SHA-256 keying and source-version locking, but poisoning can still occur if:

- Input sanitization is bypassed (injection through query parameters)
- A compromised LLM provider returns manipulated responses
- Source data is tampered with before cache population
- An attacker uses a valid API key to deliberately seed bad cache entries

### Detection Indicators

- Users report incorrect, offensive, or suspicious responses from cached queries
- Output filter warnings in application logs (`grep "security_event" logs`)
- SQL injection pattern detection triggered (`injection_blocked` events in audit log)
- Cache hit ratio anomalies (sudden spike in cache hits for queries that should miss)
- Unexpected cache entries with unusual content length or structure
- Source-version mismatch warnings during serve-time verification

### Where to look

```sql
-- Check for recently created cache entries (answer_cache table)
SELECT id, query_hash, created_at, source_manifest_hash, hit_count
FROM answer_cache
ORDER BY created_at DESC
LIMIT 50;

-- Look for cache entries created by a suspect actor/key
-- (correlate with audit_events)
SELECT ae.timestamp, ae.actor, ae.source_ip, ae.action, ae.details_json
FROM audit_events ae
WHERE ae.action LIKE '%cache%' OR ae.action LIKE '%query%'
ORDER BY ae.timestamp DESC
LIMIT 100;
```

```bash
# Check gateway logs for sanitization warnings
docker logs bitmod-gateway 2>&1 | grep -i "injection_blocked\|sanitiz\|security_event"

# Check for unusual query patterns
docker logs bitmod-gateway 2>&1 | grep -i "cache_hit\|cache_store" | tail -50
```

---

## 2. Containment

### 2a. Invalidate specific poisoned cache entries

```sql
-- If you know the query hash of the poisoned entry
DELETE FROM answer_cache WHERE query_hash = '<poisoned_hash>';

-- If you know the approximate time window of poisoning
DELETE FROM answer_cache
WHERE created_at > '<start_time>'
  AND created_at < '<end_time>';

-- If you know the source that was poisoned
DELETE FROM answer_cache
WHERE source_manifest_hash = '<compromised_source_hash>';
```

### 2b. Invalidate a broader scope

```python
# Using the Bitmod invalidation API
from bitmod.invalidation import InvalidationEngine

engine = InvalidationEngine(db_backend)

# Invalidate by pattern (e.g., all entries matching a topic)
engine.invalidate_by_pattern("*<compromised_topic>*")

# Invalidate all entries from a specific source
engine.invalidate_by_source("<source_id>")
```

### 2c. Emergency: flush entire cache

Use only if scope of poisoning is unknown or widespread:

```sql
-- SQLite
DELETE FROM answer_cache;

-- PostgreSQL
TRUNCATE answer_cache;
```

```bash
# Also flush Redis cache if used
docker exec bitmod-redis redis-cli FLUSHDB
```

**WARNING:** Full cache flush will temporarily increase LLM API costs as all queries become cache misses. Monitor API spend after flushing.

### 2d. Block the attacker

If the poisoning was done through a compromised API key:

1. Revoke the key immediately (see `api-key-compromise.md` runbook)
2. Block the source IP if known:
   ```bash
   # At application level, add to rate limiter deny list
   # At infrastructure level:
   sudo iptables -A INPUT -s <attacker_ip> -j DROP
   ```

---

## 3. Investigation

### 3a. Trace the original poisoned query

```sql
-- Find the original request that created the poisoned cache entry
-- Cross-reference audit_events with the cache entry creation time
SELECT ae.timestamp, ae.actor, ae.source_ip, ae.action, ae.details_json
FROM audit_events ae
WHERE ae.timestamp BETWEEN '<entry_created_at - 5 seconds>' AND '<entry_created_at + 5 seconds>'
ORDER BY ae.timestamp ASC;
```

### 3b. Determine the poisoning vector

Check each layer of defense:

1. **Input sanitization**: Was the malicious content in the original query, or was a clean query poisoned by the response?
   ```bash
   # Check if sanitization was bypassed
   docker logs bitmod-gateway 2>&1 | grep "sanitiz" | grep "<timestamp_window>"
   ```

2. **LLM provider response**: Was the upstream LLM provider compromised or returning unexpected results?
   ```bash
   # Check for unusual LLM responses
   docker logs bitmod-chat 2>&1 | grep "llm_response\|provider_error" | grep "<timestamp_window>"
   ```

3. **Source data tampering**: Was the ingested source data modified?
   ```sql
   -- Check source data integrity via manifest hashes
   SELECT * FROM source_manifests
   WHERE updated_at > '<suspect_start_time>'
   ORDER BY updated_at DESC;
   ```

4. **Cache key collision**: Did an attacker craft a query that produces the same cache key as a legitimate query?
   ```python
   # Verify cache key uniqueness
   from bitmod.cache_engine import compute_cache_key
   legitimate_key = compute_cache_key(legitimate_query, params)
   suspect_key = compute_cache_key(suspect_query, params)
   assert legitimate_key != suspect_key, "Cache key collision detected!"
   ```

### 3c. Assess blast radius

```sql
-- How many users were served the poisoned response?
SELECT hit_count, created_at, last_hit_at
FROM answer_cache
WHERE id = '<poisoned_entry_id>';

-- Were there similar poisoned entries?
SELECT id, query_hash, created_at, hit_count
FROM answer_cache
WHERE created_at BETWEEN '<window_start>' AND '<window_end>'
ORDER BY hit_count DESC;
```

---

## 4. Prevention Review

After containment and investigation, review these controls:

### Input validation

- [ ] `sanitize_input()` is applied to all user-facing query inputs
- [ ] `detect_sql_injection()` is active as a defense-in-depth layer
- [ ] `sanitize_for_html()` is used when rendering cached content in HTML contexts
- [ ] Content length limits (`MAX_INPUT_LENGTH = 10,000`) are enforced

### Cache integrity

- [ ] Source-version locking is active (cache entries are tied to source manifest hashes)
- [ ] Serve-time double verification is enabled (re-verify source integrity on cache hit)
- [ ] Cache TTLs are configured appropriately (stale entries expire automatically)
- [ ] Cache entry metadata includes the creating actor for forensic tracing

### Output filtering

- [ ] Responses are checked for known malicious patterns before caching
- [ ] Anomalous response lengths trigger review (e.g., response 10x longer than similar queries)
- [ ] Content-type headers are set correctly to prevent MIME-type confusion

### Monitoring

- [ ] Alert on injection_blocked security events exceeding threshold
- [ ] Alert on unusual cache write patterns (e.g., >N new entries per minute from one source)
- [ ] Alert on cache hit ratio anomalies (sudden changes may indicate poisoning or flushing)

---

## 5. Recovery Verification

After remediation:

```bash
# 1. Verify the poisoned entries are gone
# Run the query that was serving poisoned content -- should get a cache miss

# 2. Verify cache integrity
curl -s http://localhost:8000/health | python -m json.tool

# 3. Monitor cache hit/miss ratio for the next hour
# Look for normal patterns returning

# 4. Spot-check cached responses for the affected query patterns
```
