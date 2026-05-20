# FHIR ID Resolve — Operational Runbook

---

## 1. Overview

The FHIR ID Resolve service translates national patient identifiers into local FHIR Patient resource IDs. It acts as a lookup proxy between the DS-Adapter and the FHIR server.

**Stack:** Python 3.12, FastAPI, Uvicorn, httpx  
**Port:** 8000 (configurable)  
**Authentication:** HTTP Basic Auth

---

## 2. Deployment

### Container Image

```bash
docker buildx build --platform linux/arm64 -t fhir-id-resolve:latest .
```

### Running

```bash
docker run --env-file .env \
  -v /path/to/config.json:/app/config.docker.json:ro \
  -e FHIR_RESOLVE_CONFIG=/app/config.docker.json \
  -p 8000:8000 \
  fhir-id-resolve:latest
```

### Kubernetes

The service is deployed to EKS. Key manifest settings:

```yaml
livenessProbe:
  httpGet:
    path: /docs   # FastAPI auto-generated docs (confirms process is alive)
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /docs
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
```

> **Note:** This service currently does not expose dedicated `/health/live` and `/health/ready` endpoints. Consider adding them per the External Provider Guidelines.

---

## 3. Configuration

The service supports two configuration methods that can be used independently or combined:

1. **Environment variables** (recommended for production / Kubernetes)
2. **JSON config file** (convenient for local development)

**Precedence:** Environment variables always override values from the config file.

If no config file exists and no env vars are set, the service will fail to start with a clear error.

### Environment Variables

All configuration can be controlled via `FHIR_RESOLVE_*` environment variables — no file mount required.

| Variable | Required | Default | Description |
|---|---|---|---|
| `FHIR_RESOLVE_CONFIG` | No | `config.json` | Path to optional JSON config file. If the file doesn't exist, env vars are used exclusively |
| `FHIR_RESOLVE_API_HOST` | No | `0.0.0.0` | Bind address |
| `FHIR_RESOLVE_API_PORT` | No | `8000` | Listen port |
| `FHIR_RESOLVE_AUTH_USERNAME` | Yes | — | Basic Auth username for incoming requests |
| `FHIR_RESOLVE_AUTH_PASSWORD` | Yes | — | Basic Auth password for incoming requests |
| `FHIR_RESOLVE_FHIR_BASE_URL` | Yes | — | Upstream FHIR server base URL |
| `FHIR_RESOLVE_FHIR_TIMEOUT_SECONDS` | No | `10.0` | HTTP timeout for upstream FHIR requests |
| `FHIR_RESOLVE_FHIR_VERIFY_SSL` | No | `true` | Verify TLS certificates (`true`/`false`) |
| `FHIR_RESOLVE_FHIR_DEFAULT_HEADERS` | No | `{}` | JSON object string of headers added to every upstream request |
| `FHIR_RESOLVE_PATIENT_ID_STRATEGY` | No | `resource_id` | `resource_id` or `identifier` |
| `FHIR_RESOLVE_PATIENT_ID_IDENTIFIER_SYSTEM` | Conditional | — | Required when strategy is `identifier` |

#### Example: Pure env-var deployment (no config file)

```bash
docker run \
  -e FHIR_RESOLVE_AUTH_USERNAME=resolver_user \
  -e FHIR_RESOLVE_AUTH_PASSWORD=secret \
  -e FHIR_RESOLVE_FHIR_BASE_URL=https://fhir-server/fhir/r4 \
  -e FHIR_RESOLVE_FHIR_DEFAULT_HEADERS='{"Accept":"application/fhir+json","Authorization":"Basic dXNlcjpwYXNz"}' \
  -p 8000:8000 \
  fhir-id-resolve:latest
```

### Configuration File (Optional)

For local development, a JSON config file can be used. The path defaults to `config.json` and can be overridden with `FHIR_RESOLVE_CONFIG`.

The config file supports `${ENV:VARIABLE_NAME}` placeholders that are resolved at startup.

```json
{
  "api": {
    "host": "0.0.0.0",
    "port": 8000
  },
  "auth": {
    "username": "${ENV:FHIR_RESOLVE_AUTH_USERNAME}",
    "password": "${ENV:FHIR_RESOLVE_AUTH_PASSWORD}"
  },
  "fhir": {
    "base_url": "https://fhir-server/fhir/r4",
    "timeout_seconds": 10.0,
    "verify_ssl": true,
    "default_headers": {
      "Accept": "application/fhir+json"
    }
  },
  "resolver": {
    "patient_id_strategy": "resource_id",
    "patient_id_identifier_system": null
  }
}
```

### Configuration Fields Reference

| Section | Field | Type | Default | Description |
|---|---|---|---|---|
| `api` | `host` | string | `0.0.0.0` | Bind address |
| `api` | `port` | int | `8000` | Listen port |
| `auth` | `username` | string | — | Basic Auth username for incoming requests |
| `auth` | `password` | string | — | Basic Auth password for incoming requests |
| `fhir` | `base_url` | string | — | Upstream FHIR server base URL |
| `fhir` | `timeout_seconds` | float | `10.0` | HTTP timeout for upstream FHIR requests |
| `fhir` | `verify_ssl` | bool | `true` | Verify TLS certificates on upstream |
| `fhir` | `default_headers` | object | `{}` | Headers added to every upstream FHIR request |
| `resolver` | `patient_id_strategy` | enum | `resource_id` | `resource_id` — use FHIR resource ID; `identifier` — use a specific identifier system |
| `resolver` | `patient_id_identifier_system` | string | `null` | Identifier system URI to extract patient ID from (required when strategy is `identifier`) |

---

## 4. Rollback

### Docker / Docker Compose

```bash
# Stop current version
docker compose down

# Run previous image tag
docker compose up -d --pull always  # with previous tag in compose file
```

### Kubernetes

```bash
# Roll back to previous revision
kubectl rollout undo deployment/fhir-id-resolve -n <namespace>

# Verify
kubectl rollout status deployment/fhir-id-resolve -n <namespace>
```

---

## 5. Monitoring & Troubleshooting

### Health Verification

```bash
# Verify the service is responding
curl -u resolver_user:change-me http://localhost:8000/api/v1/resolve \
  -H "Content-Type: application/json" \
  -d '{"national_id": {"system": "http://example.com/id", "value": "test"}}'
```

### Common Issues

| Symptom | Likely Cause | Resolution |
|---|---|---|
| `503` on resolve | Upstream FHIR server unreachable | Check `fhir.base_url`, network connectivity, and FHIR server health |
| `401` on all requests | Wrong Basic Auth credentials | Verify `auth.username` / `auth.password` in config match the caller's credentials |
| Startup crash: "Configuration file not found" | `FHIR_RESOLVE_CONFIG` points to missing file | Verify the config file is mounted correctly |
| Startup crash: "Environment variable X is required" | Missing env var referenced by `${ENV:...}` | Set the required environment variable |
| `409` on resolve | Multiple active patients with same identifier | Data quality issue — investigate in the FHIR server |
| Timeout errors | FHIR server slow to respond | Increase `fhir.timeout_seconds` or investigate FHIR server performance |

### Logs

Logs are written to `stdout`. In Kubernetes, access via:

```bash
kubectl logs -f deployment/fhir-id-resolve -n <namespace>
```

---

## 6. Scaling

The service is stateless and can be horizontally scaled. Recommended HPA settings:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fhir-id-resolve
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fhir-id-resolve
  minReplicas: 2
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

---

## 7. Dependencies

| Dependency | Purpose | Failure Impact |
|---|---|---|
| Upstream FHIR Server | Patient lookup | All resolve requests return `503` |

The service has no database, cache, or message broker dependencies.

---

## 8. Graceful Shutdown

On `SIGTERM`, Uvicorn will:
1. Stop accepting new connections.
2. Wait for in-flight requests to complete.
3. Shut down.

Ensure the Kubernetes `terminationGracePeriodSeconds` is set to at least 30 seconds.
