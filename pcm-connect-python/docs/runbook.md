# PCM Connect (DS-Adapter) — Operational Runbook

---

## 1. Overview

The DS-Adapter is a FHIR reverse proxy that sits between external consumers (via PCM) and the internal FHIR server. It handles token introspection, patient ID resolution, JWT minting, audit logging, and response verification.

**Stack:** Python 3.11, FastAPI, Uvicorn, httpx, OpenTelemetry  
**Port:** 8000 (configurable)  
**Authentication:** Bearer token (PCM-issued) on `/fhir/*`; unauthenticated on operational endpoints

---

## 2. Secrets Management

> **IMPORTANT:** All secrets and sensitive configuration values MUST be stored in a secrets manager (AWS Secrets Manager, HashiCorp Vault, or equivalent) and injected into the container as environment variables at runtime.

**Do NOT:**
- Hardcode secrets in config files, Dockerfiles, or source code
- Commit `.env` files with real credentials to the repository
- Bake secrets into container images

**Do:**
- Use Kubernetes `ExternalSecret` or CSI Secrets Store Driver to bind secrets from AWS Secrets Manager / Vault to environment variables
- Reference secrets only via environment variables in the application
- Rotate secrets periodically and ensure the application picks up new values on restart

### Secrets that MUST be in Secrets Manager

| Secret | Env Variable | Description |
|---|---|---|
| JWT signing private key | `DS_ADAPTER_JWT_SIGNING_KEY` | PEM-encoded EC/RSA private key for minting internal JWTs |
| PCM client private key | `DS_ADAPTER_PCM_CLIENT_KEY` | PEM-encoded private key for mTLS client authentication to PCM |
| PCM client certificate | `DS_ADAPTER_PCM_CLIENT_CERT` | PEM-encoded certificate for mTLS to PCM |
| PCM CA certificate | `DS_ADAPTER_PCM_CA_CERT` | Root CA certificate for verifying PCM server |
| FHIR ID Resolve credentials | (configured in ID Replacement service) | Basic Auth credentials for the ID Replacement service |

### Example: Kubernetes ExternalSecret

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: ds-adapter-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: ds-adapter-secrets
  data:
    - secretKey: DS_ADAPTER_JWT_SIGNING_KEY
      remoteRef:
        key: /prod/ds-adapter/jwt-signing-key
    - secretKey: DS_ADAPTER_PCM_CLIENT_KEY
      remoteRef:
        key: /prod/ds-adapter/pcm-client-key
    - secretKey: DS_ADAPTER_PCM_CLIENT_CERT
      remoteRef:
        key: /prod/ds-adapter/pcm-client-cert
    - secretKey: DS_ADAPTER_PCM_CA_CERT
      remoteRef:
        key: /prod/ds-adapter/pcm-ca-cert
```

---

## 3. Configuration

The service supports two configuration methods:

1. **Environment variables** (recommended for production / Kubernetes) — prefix: `DS_ADAPTER_`
2. **YAML config file** (convenient for local development)

**Precedence:** Environment variables always override values from the YAML file.

The env var naming convention is schema-driven: `DS_ADAPTER_<SECTION>_<FIELD>` in uppercase. For example, `pcm.base_url` maps to `DS_ADAPTER_PCM_BASE_URL`, and `fhir_server.timeout_seconds` maps to `DS_ADAPTER_FHIR_SERVER_TIMEOUT_SECONDS`.

### 3.1 Minimal Production Deployment (env vars only)

A YAML file is still required as a base (it provides defaults and structure), but every value can be overridden via environment variables. In production, use a minimal `config.yaml` baked into the image and control all environment-specific values through env vars:

```bash
docker run \
  -e DS_ADAPTER_PCM_BASE_URL=https://pcm-prod:4501 \
  -e DS_ADAPTER_FHIR_SERVER_BASE_URL=https://fhir-prod:8080 \
  -e DS_ADAPTER_ID_REPLACEMENT_BASE_URL=http://id-resolve:8000 \
  -e DS_ADAPTER_JWT_ISSUER=https://ds-adapter.prod.example.com \
  -e DS_ADAPTER_JWT_SIGNING_KEY=/secrets/jwt-signing.key \
  -e DS_ADAPTER_PCM_CLIENT_KEY=/secrets/pcm-client.key \
  -e DS_ADAPTER_PCM_CLIENT_CERT=/secrets/pcm-client.crt \
  -e DS_ADAPTER_PCM_CA_CERT=/secrets/pcm-ca.crt \
  -e DS_ADAPTER_CLIENT_ID=https://my-org.example.com/oauth/client \
  -e DS_ADAPTER_OTEL_ENDPOINT=http://otel-collector:4317 \
  -e DS_ADAPTER_LOGGING_LEVEL=info \
  -p 8000:8000 \
  ds-adapter:latest
```

---

## 4. Environment Variables — Complete Reference

### 4.1 Core / Startup

| Env Variable | Required | Secret | Default | Description |
|---|---|---|---|---|
| `DS_ADAPTER_CONFIG_PATH` | No | No | `config.yaml` | Path to the YAML config file |
| `DS_ADAPTER_CLIENT_ID` | Yes | No | `ds-adapter` | OAuth2 client ID (used as `iss`/`sub` in client_assertion JWT to PCM) |

### 4.2 Server

| Env Variable | Required | Secret | Default | Description |
|---|---|---|---|---|
| `DS_ADAPTER_SERVER_HOST` | No | No | `0.0.0.0` | Bind address |
| `DS_ADAPTER_SERVER_PORT` | No | No | `8000` | Listen port |
| `DS_ADAPTER_SERVER_SHUTDOWN_TIMEOUT_SECONDS` | No | No | `30` | Max seconds to wait for in-flight requests during graceful shutdown |

### 4.3 PCM (Patient Consent Manager)

| Env Variable | Required | Secret | Default | Description |
|---|---|---|---|---|
| `DS_ADAPTER_PCM_BASE_URL` | Yes | No | — | PCM server base URL |
| `DS_ADAPTER_PCM_TOKEN_ENDPOINT` | No | No | `/token` | OAuth2 token endpoint path on PCM |
| `DS_ADAPTER_PCM_INTROSPECT_ENDPOINT` | No | No | `/introspect` | Token introspection endpoint path on PCM |
| `DS_ADAPTER_PCM_MTLS_CLIENT` | No | No | `true` | Enable mTLS for PCM connections |
| `DS_ADAPTER_PCM_CLIENT_ASSERTION_ALGORITHM` | No | No | `ES256` | Algorithm for client_assertion JWT (`ES256` / `RS256`) |
| `DS_ADAPTER_PCM_VERIFY_HOSTNAME` | No | No | `true` | Verify PCM server hostname against certificate SAN |
| `DS_ADAPTER_PCM_INTROSPECT_AUTH_METHOD` | No | No | `bearer` | Auth method for `/introspect`: `bearer` or `mtls` |
| `DS_ADAPTER_PCM_TOKEN_RESOURCE` | No | No | `null` | RFC 8707 resource indicator for `/token` requests |
| `DS_ADAPTER_PCM_CLIENT_CERT` | Yes (if mTLS) | **Yes** | — | Path or PEM content of mTLS client certificate |
| `DS_ADAPTER_PCM_CLIENT_KEY` | Yes (if mTLS) | **Yes** | — | Path or PEM content of mTLS client private key |
| `DS_ADAPTER_PCM_CA_CERT` | Yes (if mTLS) | **Yes** | — | Path or PEM content of CA certificate for PCM verification |

### 4.4 FHIR Server

| Env Variable | Required | Secret | Default | Description |
|---|---|---|---|---|
| `DS_ADAPTER_FHIR_SERVER_BASE_URL` | Yes | No | — | Internal FHIR server base URL |
| `DS_ADAPTER_FHIR_SERVER_PROTOCOL` | No | No | `https` | `http` or `https` |
| `DS_ADAPTER_FHIR_SERVER_TIMEOUT_SECONDS` | No | No | `30` | HTTP timeout for FHIR requests |

### 4.5 ID Replacement (FHIR ID Resolve)

| Env Variable | Required | Secret | Default | Description |
|---|---|---|---|---|
| `DS_ADAPTER_ID_REPLACEMENT_BASE_URL` | Yes | No | — | FHIR ID Resolve service base URL |
| `DS_ADAPTER_ID_REPLACEMENT_ENDPOINT` | No | No | `/api/v1/resolve` | Resolve endpoint path |
| `DS_ADAPTER_ID_REPLACEMENT_TIMEOUT_SECONDS` | No | No | `1.0` | HTTP timeout per attempt |
| `DS_ADAPTER_ID_REPLACEMENT_RETRIES` | No | No | `3` | Number of retry attempts on failure |
| `DS_ADAPTER_ID_REPLACEMENT_RETRY_BACKOFF_SECONDS` | No | No | `0.5` | Backoff between retries |

### 4.6 JWT

| Env Variable | Required | Secret | Default | Description |
|---|---|---|---|---|
| `DS_ADAPTER_JWT_ALGORITHM` | No | No | `ES256` | Signing algorithm (`ES256` / `RS256`) |
| `DS_ADAPTER_JWT_ISSUER` | No | No | `ds-adapter` | JWT `iss` claim. Must match the value the FHIR server trusts |
| `DS_ADAPTER_JWT_AUDIENCE` | No | No | `null` (falls back to `fhir_server.base_url`) | JWT `aud` claim. Comma-separated for multiple values |
| `DS_ADAPTER_JWT_EXPIRY_SECONDS` | No | No | `300` | JWT lifetime in seconds |
| `DS_ADAPTER_JWT_SIGNING_KEY` | Yes | **Yes** | — | PEM-encoded private key or path to PEM file |

### 4.7 Metadata (Discovery Endpoints)

| Env Variable | Required | Secret | Default | Description |
|---|---|---|---|---|
| `DS_ADAPTER_METADATA_ENABLED` | No | No | `true` | Enable `/.well-known/*` endpoints |
| `DS_ADAPTER_METADATA_JWKS_URI` | No | No | `{issuer}/.well-known/jwks.json` | Override advertised JWKS URL |
| `DS_ADAPTER_METADATA_AUTHORIZATION_ENDPOINT` | No | No | `null` | Optional authorization endpoint (usually PCM) |
| `DS_ADAPTER_METADATA_TOKEN_ENDPOINT` | No | No | `null` | Optional token endpoint (usually PCM) |
| `DS_ADAPTER_METADATA_INTROSPECTION_ENDPOINT` | No | No | `null` | Optional introspection endpoint |

### 4.8 Audit

| Env Variable | Required | Secret | Default | Description |
|---|---|---|---|---|
| `DS_ADAPTER_AUDIT_ENABLED` | No | No | `true` | Enable/disable audit logging |
| `DS_ADAPTER_AUDIT_FORMAT` | No | No | `json` | Audit format: `json` or `cef` |
| `DS_ADAPTER_AUDIT_INCLUDE_RESPONSE` | No | No | `false` | Include FHIR response body in audit |
| `DS_ADAPTER_AUDIT_TARGETS_SYSLOG_ENABLED` | No | No | `false` | Enable syslog audit target |
| `DS_ADAPTER_AUDIT_TARGETS_SYSLOG_HOST` | No | No | `localhost` | Syslog server host |
| `DS_ADAPTER_AUDIT_TARGETS_SYSLOG_PORT` | No | No | `514` | Syslog server port |
| `DS_ADAPTER_AUDIT_TARGETS_SYSLOG_PROTOCOL` | No | No | `udp` | `udp` or `tcp` |
| `DS_ADAPTER_AUDIT_TARGETS_FILE_ENABLED` | No | No | `true` | Enable file audit target |
| `DS_ADAPTER_AUDIT_TARGETS_FILE_PATH` | No | No | `/var/log/adapter/audit.log` | Audit log file path |
| `DS_ADAPTER_AUDIT_TARGETS_FILE_ROTATION` | No | No | `daily` | `daily`, `hourly`, or `none` |
| `DS_ADAPTER_AUDIT_TARGETS_FILE_MAX_FILES` | No | No | `30` | Max rotated files to retain |
| `DS_ADAPTER_AUDIT_TARGETS_KAFKA_ENABLED` | No | No | `false` | Enable Kafka audit target |
| `DS_ADAPTER_AUDIT_TARGETS_KAFKA_BROKERS` | No | No | `kafka:9092` | Kafka broker addresses |
| `DS_ADAPTER_AUDIT_TARGETS_KAFKA_TOPIC` | No | No | `ds-adapter-audit` | Kafka topic |

### 4.9 Logging

| Env Variable | Required | Secret | Default | Description |
|---|---|---|---|---|
| `DS_ADAPTER_LOGGING_LEVEL` | No | No | `info` | Log level: `debug`, `info`, `warning`, `error` |
| `DS_ADAPTER_LOGGING_FORMAT` | No | No | `json` | Output format: `json` (ECS) or `text` |

### 4.10 OpenTelemetry

| Env Variable | Required | Secret | Default | Description |
|---|---|---|---|---|
| `DS_ADAPTER_OTEL_ENABLED` | No | No | `true` | Enable/disable tracing |
| `DS_ADAPTER_OTEL_EXPORTER` | No | No | `otlp` | Exporter type: `otlp` or `none` |
| `DS_ADAPTER_OTEL_ENDPOINT` | No | No | `http://otel-collector:4317` | OTLP collector endpoint (gRPC) |
| `DS_ADAPTER_OTEL_SERVICE_NAME` | No | No | `ds-adapter` | Service name in traces |
| `DS_ADAPTER_OTEL_SAMPLE_RATE` | No | No | `1.0` | Sampling rate (0.0–1.0) |

### 4.11 Verification

| Env Variable | Required | Secret | Default | Description |
|---|---|---|---|---|
| `DS_ADAPTER_VERIFICATION_ENABLED` | No | No | `true` | Enable response verification |

> **Note:** `verification.forbidden_labels` is a list and cannot be easily set via a single env var. Configure it in the YAML file.

---

## 5. YAML Config File (Local Development)

For local development, a `config.yaml` provides a convenient way to set all values in one place. The file path defaults to `config.yaml` and can be overridden with `DS_ADAPTER_CONFIG_PATH`.

See the repository's `config.yaml` for a fully commented example with all sections.

**Remember:** Any value in the YAML can be overridden by setting the corresponding `DS_ADAPTER_*` environment variable.

---

## 6. Deployment

### Container Image

```bash
docker buildx build --platform linux/arm64 -t ds-adapter:latest .
```

### Running with Docker

```bash
docker run --env-file .env \
  -p 8000:8000 \
  ds-adapter:latest
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ds-adapter
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: ds-adapter
          image: ds-adapter:1.0.0
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: ds-adapter-config
            - secretRef:
                name: ds-adapter-secrets
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 15
            failureThreshold: 3
          resources:
            requests:
              cpu: 200m
              memory: 256Mi
            limits:
              cpu: 1000m
              memory: 512Mi
      terminationGracePeriodSeconds: 30
```

### Example ConfigMap (non-secret values)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ds-adapter-config
data:
  DS_ADAPTER_PCM_BASE_URL: "https://pcm-prod:4501"
  DS_ADAPTER_FHIR_SERVER_BASE_URL: "https://fhir-prod:8080"
  DS_ADAPTER_ID_REPLACEMENT_BASE_URL: "http://fhir-id-resolve:8000"
  DS_ADAPTER_JWT_ISSUER: "https://ds-adapter.prod.example.com"
  DS_ADAPTER_JWT_AUDIENCE: "https://fhir-prod:8080/fhir/r4"
  DS_ADAPTER_CLIENT_ID: "https://my-org.example.com/oauth/client"
  DS_ADAPTER_PCM_CLIENT_ASSERTION_ALGORITHM: "RS256"
  DS_ADAPTER_PCM_INTROSPECT_AUTH_METHOD: "bearer"
  DS_ADAPTER_OTEL_ENDPOINT: "http://otel-collector:4317"
  DS_ADAPTER_LOGGING_LEVEL: "info"
  DS_ADAPTER_AUDIT_ENABLED: "true"
  DS_ADAPTER_AUDIT_TARGETS_FILE_ENABLED: "false"
  DS_ADAPTER_AUDIT_TARGETS_KAFKA_ENABLED: "true"
  DS_ADAPTER_AUDIT_TARGETS_KAFKA_BROKERS: "kafka:9092"
```

---

## 7. Rollback

### Docker Compose

```bash
docker compose down
# Update image tag in docker-compose.yaml to previous version
docker compose up -d
```

### Kubernetes

```bash
# Roll back to previous revision
kubectl rollout undo deployment/ds-adapter -n <namespace>

# Verify rollback
kubectl rollout status deployment/ds-adapter -n <namespace>

# Check pods are healthy
kubectl get pods -n <namespace> -l app=ds-adapter
```

### Rollback Checklist

1. Verify the previous image tag is available in ECR
2. Roll back the deployment
3. Confirm `/health` returns `200`
4. Confirm `/ready` returns `200` (all dependencies reachable)
5. Verify a test FHIR request flows end-to-end
6. Check logs for errors

---

## 8. Monitoring

### Health Endpoints

| Endpoint | Purpose | Expected Response |
|---|---|---|
| `GET /health` | Liveness — process is alive | `200 {"status": "ok"}` |
| `GET /ready` | Readiness — dependencies reachable | `200 {"status": "ready", "fhir_server": "ok", "pcm": "ok"}` |
| `GET /metrics` | Prometheus metrics | Prometheus text format |

### Key Metrics

| Metric | Description | Alert Threshold |
|---|---|---|
| PCM introspect duration | Time to introspect tokens | p95 > 2s |
| ID replacement duration | Time to resolve patient ID | p95 > 1s |
| FHIR forward duration | Time for upstream FHIR response | p95 > 5s |
| HTTP 5xx rate | Server errors | > 1% of requests |
| HTTP 503 from `/ready` | Dependency failure | Any occurrence |

### Dashboards

- **Request flow:** Total requests, latency percentiles, error rates by endpoint
- **Dependencies:** PCM introspect latency, ID replacement latency, FHIR forward latency
- **Infrastructure:** CPU, memory, pod restarts, HPA scaling events

---

## 9. Troubleshooting

### Common Issues

| Symptom | Likely Cause | Resolution |
|---|---|---|
| `/ready` returns 503 with `pcm: error` | PCM server unreachable | Check `DS_ADAPTER_PCM_BASE_URL`, network connectivity, mTLS certificates |
| `/ready` returns 503 with `fhir_server: error` | FHIR server unreachable | Check `DS_ADAPTER_FHIR_SERVER_BASE_URL`, network connectivity |
| `AUTH_001` on FHIR requests | Missing/malformed Bearer token | Caller must provide `Authorization: Bearer <token>` |
| `AUTH_002` on FHIR requests | PCM introspection didn't return patient | Check PCM token validity, consent status |
| `CFG_001` on FHIR requests | JWT signing key not configured | Set `DS_ADAPTER_JWT_SIGNING_KEY` env var |
| Startup crash | Missing required config or env vars | Check logs for specific missing field |
| mTLS handshake failure | Certificate mismatch or expired | Verify cert/key pair, check expiry dates, ensure CA cert matches |
| JWT rejected by FHIR server | Issuer/audience mismatch | Ensure `DS_ADAPTER_JWT_ISSUER` and `DS_ADAPTER_JWT_AUDIENCE` match FHIR server configuration |
| Forbidden label in response | Verification caught restricted data | Check consent scope — patient may not have consented to this data category |

### Log Investigation

```bash
# Kubernetes
kubectl logs -f deployment/ds-adapter -n <namespace>

# Filter for errors
kubectl logs deployment/ds-adapter -n <namespace> | jq 'select(.level == "error")'

# Search by correlation ID
kubectl logs deployment/ds-adapter -n <namespace> | jq 'select(.correlation_id == "abc-123")'
```

### Connectivity Checks

```bash
# From within the pod
kubectl exec -it <pod> -n <namespace> -- python -c "
import httpx
r = httpx.get('http://fhir-id-resolve:8000/docs')
print(r.status_code)
"
```

---

## 10. Scaling

The service is stateless and horizontally scalable.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ds-adapter
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ds-adapter
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

**Scaling considerations:**
- Each pod maintains its own HTTP connection pools to PCM, FHIR server, and ID Replacement service
- mTLS handshakes are expensive — connection reuse is critical
- Monitor PCM rate limits when scaling up

---

## 11. Graceful Shutdown

On `SIGTERM`:
1. The adapter stops accepting new connections
2. In-flight requests are allowed to complete (up to `DS_ADAPTER_SERVER_SHUTDOWN_TIMEOUT_SECONDS`, default 30s)
3. Audit service flushes pending events
4. HTTP clients (PCM, FHIR, ID Replacement) are closed
5. Process exits

Ensure Kubernetes `terminationGracePeriodSeconds` ≥ `DS_ADAPTER_SERVER_SHUTDOWN_TIMEOUT_SECONDS`.

---

## 12. Dependencies

| Dependency | Purpose | Failure Impact |
|---|---|---|
| PCM Server | Token introspection | All FHIR proxy requests fail (401/503) |
| FHIR ID Resolve | Patient ID resolution | All FHIR proxy requests fail (503) |
| FHIR Server (upstream) | Data source | FHIR responses return upstream error |
| OTel Collector | Trace export | Traces lost (non-blocking, service continues) |
| Kafka (if enabled) | Audit event streaming | Audit events may be lost (non-blocking) |
| Syslog (if enabled) | Audit event forwarding | Audit events may be lost (non-blocking) |

---

## 13. Certificate Rotation

When rotating mTLS certificates:

1. Generate new certificate/key pair
2. Update the secret in AWS Secrets Manager / Vault
3. Restart pods (rolling restart): `kubectl rollout restart deployment/ds-adapter -n <namespace>`
4. Verify `/ready` returns 200
5. Verify a test FHIR request succeeds end-to-end
6. Remove old certificate from PCM trust store (after confirming all pods use the new cert)

For JWT signing key rotation:
1. Generate new key pair
2. Update `DS_ADAPTER_JWT_SIGNING_KEY` in Secrets Manager
3. Register the new public key with the FHIR server (IRIS) trust configuration
4. Restart pods
5. After all pods are using the new key, remove the old public key from the FHIR server trust store
