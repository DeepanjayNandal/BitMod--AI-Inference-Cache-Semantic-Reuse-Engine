# BitMod Deployment Guide

## Quick Start with Docker Compose

The fastest way to run BitMod locally:

```bash
# From the project root
docker compose -f deploy/docker-compose.yaml up

# With PostgreSQL
docker compose -f deploy/docker-compose.yaml --profile postgres up

# With Redis (for distributed rate limiting)
docker compose -f deploy/docker-compose.yaml --profile redis up

# Everything
docker compose -f deploy/docker-compose.yaml --profile postgres --profile redis up
```

Gateway is available at `http://localhost:8000`. Verify with:

```bash
curl http://localhost:8000/health
```

## Kubernetes Deployment with Helm

### Prerequisites

- Kubernetes cluster (1.24+)
- Helm 3.x
- Container images pushed to your registry

### Install

```bash
# Default install (SQLite, no ingress)
helm install bitmod ./deploy/helm/bitmod

# With custom values
helm install bitmod ./deploy/helm/bitmod -f my-values.yaml

# With PostgreSQL backend
helm install bitmod ./deploy/helm/bitmod \
  --set database.backend=postgresql \
  --set database.postgresql.enabled=true \
  --set database.postgresql.host=my-pg-host \
  --set database.postgresql.database=bitmod

# Create the database password secret first
kubectl create secret generic bitmod-db \
  --from-literal=password='your-db-password'

# With ingress
helm install bitmod ./deploy/helm/bitmod \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=bitmod.example.com \
  --set ingress.hosts[0].paths[0].path=/ \
  --set ingress.hosts[0].paths[0].pathType=Prefix
```

### Retrieve the Admin API Key

If `auth.autoGenerateKey` is true (the default), a random API key is generated at install time:

```bash
kubectl get secret bitmod-auth -o jsonpath='{.data.admin-api-key}' | base64 -d; echo
```

### Upgrade

```bash
helm upgrade bitmod ./deploy/helm/bitmod -f my-values.yaml
```

### Uninstall

```bash
helm uninstall bitmod
# PVCs are retained by default — delete manually if needed
kubectl delete pvc bitmod-data
```

## Configuration Reference

### Core

| Parameter | Description | Default |
|---|---|---|
| `image.repository` | Container image base | `ghcr.io/bitmoderator/bitmod` |
| `image.tag` | Image tag | `latest` |
| `gateway.replicas` | Gateway pod count | `1` |
| `gateway.port` | Gateway listen port | `8000` |
| `chat.replicas` | Chat pod count | `1` |
| `chat.port` | Chat listen port | `8001` |

### Database

| Parameter | Description | Default |
|---|---|---|
| `database.backend` | `sqlite` or `postgresql` | `sqlite` |
| `database.sqlite.storageSize` | PVC size for SQLite | `1Gi` |
| `database.postgresql.enabled` | Enable PostgreSQL connection | `false` |
| `database.postgresql.host` | PostgreSQL hostname | `""` |
| `database.postgresql.port` | PostgreSQL port | `5432` |
| `database.postgresql.database` | Database name | `bitmod` |
| `database.postgresql.username` | Database user | `bitmod` |
| `database.postgresql.existingSecret` | Secret with `password` key | `""` |

### LLM

| Parameter | Description | Default |
|---|---|---|
| `llm.primary` | Primary LLM provider | `ollama` |
| `llm.primaryModel` | Primary model name | `llama3.2` |
| `llm.fallback` | Fallback LLM provider | `ollama` |
| `llm.fallbackModel` | Fallback model name | `llama3.2` |
| `llm.existingSecret` | Secret with API keys (e.g., `ANTHROPIC_API_KEY`) | `""` |

### Networking

| Parameter | Description | Default |
|---|---|---|
| `ingress.enabled` | Create Ingress resource | `false` |
| `ingress.className` | Ingress class | `nginx` |
| `cors.origins` | Comma-separated allowed origins | `""` (deny all) |
| `cors.strict` | Strict CORS mode | `true` |

### Security and Auth

| Parameter | Description | Default |
|---|---|---|
| `auth.enabled` | Enable API key authentication | `true` |
| `auth.autoGenerateKey` | Generate admin key on install | `true` |
| `rateLimits.enabled` | Enable rate limiting | `true` |
| `rateLimits.requestsPerMinute` | Rate limit per key | `60` |

### Observability

| Parameter | Description | Default |
|---|---|---|
| `observability.jsonLogs` | JSON-formatted logs | `true` |
| `observability.metrics` | Expose Prometheus metrics | `true` |
| `observability.otel.enabled` | OpenTelemetry export | `false` |
| `observability.otel.endpoint` | OTLP collector endpoint | `""` |

## TLS Termination

BitMod does not terminate TLS itself. Use one of the following reverse proxies in front of the gateway.

### Option 1: Caddy (recommended for simplicity)

Caddy automatically provisions and renews Let's Encrypt certificates. Add a `caddy` profile to your Compose file:

```yaml
services:
  caddy:
    image: caddy:2-alpine
    profiles: ["tls"]
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - caddy_data:/data
      - caddy_config:/config
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
    networks:
      - bitmod
    restart: unless-stopped

volumes:
  caddy_data:
  caddy_config:
```

With a `Caddyfile`:

```
bitmod.example.com {
    reverse_proxy bitmod-gateway:8000
}
```

Start with:

```bash
docker compose -f deploy/docker-compose.yaml --profile tls up
```

### Option 2: nginx

Use nginx with manually provisioned or certbot-managed certificates:

```nginx
server {
    listen 443 ssl http2;
    server_name bitmod.example.com;

    ssl_certificate     /etc/letsencrypt/live/bitmod.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bitmod.example.com/privkey.pem;

    location / {
        proxy_pass http://bitmod-gateway:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support for chat streaming
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}

server {
    listen 80;
    server_name bitmod.example.com;
    return 301 https://$host$request_uri;
}
```

### Option 3: Cloud Load Balancer

On AWS, GCP, or Azure, terminate TLS at the managed load balancer and forward plain HTTP to the gateway on port 8000. This is the simplest option when running on a cloud provider:

- **AWS**: Application Load Balancer with ACM certificate
- **GCP**: Cloud Load Balancer with Google-managed certificate
- **Azure**: Application Gateway with Key Vault certificate

In all cases, set `X-Forwarded-Proto: https` so the gateway knows the original connection was encrypted.

When using Kubernetes, enable ingress with TLS in your values file (see `values-production.yaml` for an example with cert-manager).

## Security Hardening Checklist

- [ ] Set `cors.origins` to your specific domains (never use `*` in production)
- [ ] Set `cors.strict: true` (default)
- [ ] Create LLM API key secrets manually rather than storing in values files
- [ ] Use `database.postgresql.existingSecret` instead of inline credentials
- [ ] Enable ingress with TLS termination
- [ ] Set resource limits appropriate to your workload
- [ ] Use a non-default `storageClass` with encryption at rest
- [ ] Enable network policies to restrict pod-to-pod traffic
- [ ] Run `helm install` with `--set auth.autoGenerateKey=true` and retrieve the key from the secret
- [ ] Rotate API keys periodically by deleting and recreating the auth secret
- [ ] Enable `observability.otel` and ship logs to a central collector
- [ ] Use Pod Security Standards (restricted profile) at the namespace level

## Scaling Guide

### Gateway (Horizontal)

The gateway is stateless and can be scaled horizontally:

```bash
helm upgrade bitmod ./deploy/helm/bitmod --set gateway.replicas=3
```

When scaling beyond 1 replica, you must use PostgreSQL (not SQLite) and enable Redis for distributed rate limiting:

```yaml
gateway:
  replicas: 3
database:
  backend: postgresql
  postgresql:
    enabled: true
    host: my-pg-host
redis:
  enabled: true
  host: my-redis-host
```

### Chat (Vertical)

The chat service holds LLM connection state and is best scaled vertically:

```yaml
chat:
  replicas: 1
  resources:
    requests:
      cpu: 1000m
      memory: 1Gi
    limits:
      cpu: 4000m
      memory: 4Gi
```

Multiple chat replicas work but require sticky sessions or a shared state backend.

### Pod Autoscaling

For automatic scaling, create an HPA:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: bitmod-gateway
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: bitmod-gateway
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

## Backup and Restore

### SQLite

Back up the PVC data:

```bash
# Create a backup pod
kubectl run bitmod-backup --image=busybox --restart=Never \
  --overrides='{"spec":{"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"bitmod-data"}}],"containers":[{"name":"backup","image":"busybox","command":["cp","/data/bitmod.db","/backup/bitmod.db"],"volumeMounts":[{"name":"data","mountPath":"/data"}]}]}}'

# Or copy directly from the running pod
kubectl cp $(kubectl get pod -l app.kubernetes.io/component=gateway -o name | head -1):/app/data/bitmod.db ./bitmod-backup.db
```

Restore:

```bash
kubectl cp ./bitmod-backup.db $(kubectl get pod -l app.kubernetes.io/component=gateway -o name | head -1):/app/data/bitmod.db
kubectl rollout restart deployment bitmod-gateway
kubectl rollout restart deployment bitmod-chat
```

### PostgreSQL

Use standard PostgreSQL backup tools:

```bash
# Backup
pg_dump -h <host> -U bitmod -d bitmod > bitmod-backup.sql

# Restore
psql -h <host> -U bitmod -d bitmod < bitmod-backup.sql
```

For production, use continuous archiving (WAL-G) or your managed database provider's built-in backup system.
