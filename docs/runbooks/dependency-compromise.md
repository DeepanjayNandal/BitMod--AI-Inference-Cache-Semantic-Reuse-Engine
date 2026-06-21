# Runbook: Dependency Compromise (Supply Chain Attack)

**Severity:** P1 (if compromised code executed in production) / P2 (if detected before execution)
**Owner:** Security On-Call + Engineering Lead
**Last Updated:** 2026-03-26

---

## 1. Detection

### 1a. Automated detection sources

- **pip-audit**: Alerts on known vulnerabilities in Python dependencies
- **Trivy**: Container image scanning for OS and application vulnerabilities
- **GitHub Dependabot / Security Advisories**: Automated PRs and alerts
- **CI pipeline failures**: `.github/workflows/ci.yml` security checks
- **PyPI / npm security advisories**: Public disclosure of compromised packages

```bash
# Run pip-audit manually
pip-audit --requirement requirements.txt

# Scan container images with Trivy
trivy image bitmod-gateway:latest
trivy image bitmod-chat:latest

# Check for known vulnerabilities in installed packages
pip-audit --format json > audit-results.json
```

### 1b. Behavioral indicators of a compromised dependency

- Unexpected outbound network connections from containers
- New environment variable reads that were not in previous versions
- Unusual file system writes (especially to `/tmp`, home directories, or dotfiles)
- Increased CPU/memory usage without traffic increase
- DNS queries to unfamiliar domains
- Processes spawned that are not part of normal application flow

```bash
# Check for unusual network connections from containers
docker exec bitmod-gateway ss -tunapl
docker exec bitmod-chat ss -tunapl

# Check for unexpected processes
docker exec bitmod-gateway ps aux
docker exec bitmod-chat ps aux

# Check for unusual DNS queries (if DNS logging is enabled)
docker exec bitmod-gateway cat /etc/resolv.conf

# Check for unexpected files written recently
docker exec bitmod-gateway find /tmp -mmin -60 -type f 2>/dev/null
docker exec bitmod-gateway find /app -mmin -60 -type f -newer /app/main.py 2>/dev/null
```

### 1c. Manual dependency review

```bash
# List all installed packages and versions
docker exec bitmod-gateway pip list --format json > installed-packages.json

# Compare against known-good baseline
diff <(cat installed-packages-baseline.json | python -m json.tool) \
     <(cat installed-packages.json | python -m json.tool)

# Check package integrity (pip verify is limited, but useful)
docker exec bitmod-gateway pip check
```

---

## 2. Rollback Procedure

### 2a. Identify the compromised package

```bash
# Which package, which version, what vulnerability?
# From pip-audit output:
pip-audit 2>&1 | grep -i "vulnerability\|compromised"

# Check when the package was last updated in your lockfile
git log --oneline -20 -- requirements.txt pyproject.toml
git diff HEAD~5 -- requirements.txt pyproject.toml
```

### 2b. Pin to last known-good version

```bash
# 1. Edit requirements.txt or pyproject.toml
#    Change: compromised-package>=1.0
#    To:     compromised-package==<last_safe_version>

# 2. For pyproject.toml dependencies, pin the exact version:
#    "httpx==0.27.0",  # Pinned: version 0.27.1 compromised
```

### 2c. Rebuild and redeploy

```bash
# Rebuild containers with pinned dependency
docker compose build --no-cache gateway chat

# Deploy the fixed images
docker compose up -d gateway chat

# Verify services are healthy
docker compose ps
curl -s http://localhost:8000/health
```

### 2d. Lock dependency resolution

```bash
# Generate a lockfile to prevent future resolution to compromised versions
pip freeze > requirements-lock.txt

# Or use pip-compile (pip-tools)
pip-compile --generate-hashes requirements.in -o requirements.txt
```

---

## 3. Audit: Did Compromised Code Execute?

### 3a. Determine exposure window

```bash
# When was the compromised version introduced?
git log --all --oneline -- requirements.txt pyproject.toml | head -20

# When was the container last rebuilt? (image creation time)
docker inspect bitmod-gateway --format '{{.Created}}'
docker inspect bitmod-chat --format '{{.Created}}'

# Cross-reference with the vulnerability disclosure date
```

### 3b. Check for indicators of exploitation

```bash
# Check container filesystem for artifacts
docker exec bitmod-gateway find / -newer /app/main.py -name "*.py" 2>/dev/null
docker exec bitmod-gateway find /tmp -type f 2>/dev/null
docker exec bitmod-gateway find /root -type f 2>/dev/null

# Check for unauthorized cron jobs
docker exec bitmod-gateway crontab -l 2>/dev/null

# Check for modified system files
docker exec bitmod-gateway find /usr/lib/python3* -newer /app/main.py -name "*.py" 2>/dev/null

# Review outbound network activity during exposure window
# (requires network logging or PCAP)
```

### 3c. Check for data exfiltration

```sql
-- Review audit events during exposure window
SELECT timestamp, event_type, actor, source_ip, action, outcome
FROM audit_events
WHERE timestamp BETWEEN '<exposure_start>' AND '<exposure_end>'
ORDER BY timestamp ASC;

-- Look for unusual data access patterns
SELECT actor, COUNT(*) as requests, COUNT(DISTINCT source_ip) as unique_ips
FROM audit_events
WHERE timestamp BETWEEN '<exposure_start>' AND '<exposure_end>'
GROUP BY actor
ORDER BY requests DESC;
```

### 3d. Check for persistence mechanisms

```bash
# Did the compromised package modify any application files?
docker exec bitmod-gateway find /app -name "*.py" -newer /app/requirements.txt 2>/dev/null

# Check for added Python packages that weren't in the original requirements
docker exec bitmod-gateway pip list --format columns | \
  diff - <(cat requirements.txt | grep -v "^#" | grep -v "^$" | sort)

# Check for modified entry points or startup scripts
docker exec bitmod-gateway cat /app/main.py | sha256sum
# Compare against known-good hash
```

### 3e. Full container image diff (thorough)

```bash
# Export the potentially compromised container filesystem
docker export bitmod-gateway > compromised-gateway.tar

# Build a clean image from the same Dockerfile with pinned deps
docker build --no-cache -t bitmod-gateway:clean -f services/gateway/Dockerfile .
docker create --name clean-gateway bitmod-gateway:clean
docker export clean-gateway > clean-gateway.tar
docker rm clean-gateway

# Compare the two
mkdir -p /tmp/diff-compromised /tmp/diff-clean
tar xf compromised-gateway.tar -C /tmp/diff-compromised
tar xf clean-gateway.tar -C /tmp/diff-clean
diff -rq /tmp/diff-compromised /tmp/diff-clean
```

---

## 4. Disclosure and Communication

### 4a. Internal communication

Notify the following immediately:

1. **Engineering team**: Which dependency, what version, exposure window
2. **Security team**: Investigation findings, IOCs
3. **Management**: Impact assessment, customer exposure

### 4b. External disclosure (if Bitmod users are affected)

If Bitmod is deployed by customers and the compromised dependency was included in distributed images:

```markdown
## Security Advisory: [Package Name] Supply Chain Compromise

**Date:** YYYY-MM-DD
**Affected Versions:** Bitmod vX.Y.Z through vX.Y.W
**Fixed Version:** Bitmod vX.Y.V
**CVE:** CVE-YYYY-NNNNN (if assigned)

### Summary
A compromised version of [package] (version X.Y.Z) was included in Bitmod
container images built between [date] and [date].

### Impact
[Description of what the compromised code could do]

### Recommended Actions
1. Update to Bitmod vX.Y.V or later
2. Rebuild containers: `docker compose build --no-cache`
3. Rotate all API keys and secrets
4. Review audit logs for the exposure window

### Detection
[How to check if you were affected]
```

### 4c. Upstream reporting

- Report to the package maintainers / registry (PyPI, npm)
- File a CVE if one hasn't been assigned
- Report to GitHub Advisory Database
- Share IOCs with the security community

---

## 5. Prevention Measures

### 5a. Ongoing

- [ ] Pin all dependency versions with hashes (`pip-compile --generate-hashes`)
- [ ] Run `pip-audit` in CI pipeline (`.github/workflows/ci.yml`)
- [ ] Run Trivy scans on container images before deployment
- [ ] Enable GitHub Dependabot alerts on the repository
- [ ] Review dependency updates before merging (no auto-merge for dependencies)

### 5b. Build integrity

- [ ] Use multi-stage Docker builds to minimize attack surface
- [ ] Sign container images (Docker Content Trust / cosign)
- [ ] Store a baseline of installed packages for comparison
- [ ] Use `--no-cache` for production builds to avoid stale layers

### 5c. Runtime protection

- [ ] Run containers as non-root users
- [ ] Use read-only filesystem where possible
- [ ] Drop all Linux capabilities except those required
- [ ] Monitor outbound network connections for anomalies
- [ ] Set `--security-opt=no-new-privileges` on containers
