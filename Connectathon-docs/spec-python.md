# DS Adapter — מפרט מלא למפתח (Python / FastAPI)

> **מטרת המסמך**: מסמך זה מכיל את כל מה שמפתח + coding agent צריכים כדי לבנות את ה-DS Adapter מאפס. הוא כולל: ארכיטקטורה, flows, data types, config, API contracts, error handling, testing — הכל במקום אחד.

---

## 1. מה זה DS Adapter?

שירות stateless שמשמש כ-**Policy Enforcement Point** עבור מקור מידע רפואי. הוא:
1. מקבל בקשה מנותן שירות (SP) עם opaque token
2. מאמת את הטוקן מול ה-PCM (מהרש"ג)
3. ממיר מזהה לאומי למזהה מטופל מקומי
4. יוצר JWT פנימי חתום
5. מזריק פרמטר אבטחה לשאילתה
6. מעביר את הבקשה ל-FHIR Server
7. מאמת שהתשובה לא מכילה מידע חסוי
8. מחזיר את התשובה

**עקרונות**: Stateless, Configuration-driven, Instance per organization, Contract-first, Observable.

---

## 2. טכנולוגיות

| רכיב | טכנולוגיה | גרסה |
|-------|-----------|-------|
| שפה | Python | 3.11+ |
| Framework | FastAPI | latest |
| HTTP Client | httpx | latest (async) |
| JWT | PyJWT + cryptography | ES256 |
| Config | pydantic-settings + PyYAML | |
| Logging | structlog | JSON structured |
| Audit (Kafka) | aiokafka | async |
| Observability | opentelemetry-sdk | OTLP exporter |
| Testing | pytest + pytest-asyncio + respx | |
| Server | uvicorn | |
| Container | Docker | python:3.11-slim |

---

## 3. מבנה פרויקט

```
ds-adapter/
├── src/
│   ├── main.py                 # FastAPI app, lifespan, middleware registration
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py         # load YAML + env override, return AppConfig
│   │   └── models.py           # Pydantic models for all config sections
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py           # catch-all FHIR proxy route + health/ready/metrics
│   │   └── dependencies.py     # FastAPI Depends: get_correlation_id, get_bearer_token
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── pcm_client.py       # get_pcm_token(), introspect_token()
│   │   ├── jwt_service.py      # mint_internal_jwt()
│   │   └── mtls.py             # create_mtls_client() → httpx.AsyncClient
│   ├── identity/
│   │   ├── __init__.py
│   │   └── id_replacement.py   # resolve_patient_id() with retry
│   ├── fhir/
│   │   ├── __init__.py
│   │   ├── client.py           # forward_to_fhir()
│   │   └── verification.py     # verify_response() — scan for forbidden labels
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── service.py          # AuditService.record() — dispatches to targets
│   │   ├── targets/
│   │   │   ├── __init__.py
│   │   │   ├── syslog.py       # SyslogTarget.send()
│   │   │   ├── file.py         # FileTarget.send()
│   │   │   └── kafka.py        # KafkaTarget.send()
│   │   └── formatters/
│   │       ├── __init__.py
│   │       ├── json_fmt.py     # format_json()
│   │       └── cef_fmt.py      # format_cef()
│   ├── errors/
│   │   ├── __init__.py
│   │   ├── catalog.py          # ERROR_CATALOG dict: code → (status, issue_code, display, diagnostics)
│   │   ├── handlers.py         # register_exception_handlers(app)
│   │   └── models.py           # build_operation_outcome(error_code) → dict
│   ├── observability/
│   │   ├── __init__.py
│   │   └── setup.py            # init_otel(app, config) — traces + metrics
│   ├── logging/
│   │   ├── __init__.py
│   │   └── setup.py            # configure_logging(level) — structlog + stdout/stderr
│   └── middleware/
│       ├── __init__.py
│       ├── correlation.py      # CorrelationMiddleware — extract/generate X-Correlation-ID
│       ├── audit_middleware.py  # AuditMiddleware — capture request/response for audit
│       └── timing.py           # TimingMiddleware — measure response time
├── tests/
│   ├── unit/
│   │   ├── test_pcm_client.py
│   │   ├── test_jwt_service.py
│   │   ├── test_id_replacement.py
│   │   ├── test_verification.py
│   │   ├── test_config.py
│   │   ├── test_error_handlers.py
│   │   └── test_correlation.py
│   ├── integration/
│   │   ├── test_happy_path.py
│   │   ├── test_auth_failures.py
│   │   ├── test_id_failures.py
│   │   ├── test_fhir_failures.py
│   │   └── test_verification_failures.py
│   └── conftest.py             # fixtures: mock_pcm, mock_fhir, mock_id_service, test_client
├── config.yaml
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── docker-compose.yaml
└── README.md
```

---

## 4. Configuration — מפרט מלא

### 4.1 config.yaml (ברירות מחדל)

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  shutdown_timeout_seconds: 30

pcm:
  base_url: "https://pcm-core:3000"
  token_endpoint: "/token"
  introspect_endpoint: "/introspect"
  token_scope: "system/*.crus"
  mtls_client: true

fhir_server:
  base_url: "https://fhir-internal:8080"
  protocol: "https"
  timeout_seconds: 30

id_replacement:
  base_url: "http://id-service:9000"
  endpoint: "/api/v1/resolve"
  timeout_seconds: 1.0
  retries: 3
  retry_backoff_seconds: 0.5

jwt:
  algorithm: "ES256"
  issuer: "ds-adapter"
  expiry_seconds: 300

audit:
  enabled: true
  format: "json"
  include_response: false
  targets:
    syslog:
      enabled: false
      host: "localhost"
      port: 514
      protocol: "udp"
    file:
      enabled: true
      path: "/var/log/adapter/audit.log"
      rotation: "daily"
      max_files: 30
    kafka:
      enabled: false
      brokers: "kafka:9092"
      topic: "ds-adapter-audit"

logging:
  level: "info"
  format: "json"

otel:
  enabled: true
  exporter: "otlp"
  endpoint: "http://otel-collector:4317"
  service_name: "ds-adapter"
  sample_rate: 1.0

verification:
  enabled: true
  forbidden_labels:
    - "http://fhir.health.gov.il/cs/il-core-main-security-label|V"
```

### 4.2 Environment Variables Override

Convention: `DS_ADAPTER_<SECTION>_<KEY>` (uppercase, underscore)

דוגמה: `DS_ADAPTER_PCM_BASE_URL` גובר על `pcm.base_url`

### 4.3 Secrets (Environment Variables — חובה)

```bash
DS_ADAPTER_PCM_CLIENT_CERT=<PEM client certificate for mTLS>
DS_ADAPTER_PCM_CLIENT_KEY=<PEM private key for mTLS>
DS_ADAPTER_PCM_CA_CERT=<PEM CA certificate>
DS_ADAPTER_JWT_SIGNING_KEY=<PEM ES256 private key for JWT signing>
DS_ADAPTER_ID_REPLACEMENT_AUTH=<org-specific credentials>
```

---

## 5. Request Flow — מפורט

### 5.1 Happy Path (Sequence)

```
1. Gateway → Adapter: GET /fhir/Observation?patient=000000018
   Headers: Authorization: Bearer <opaque_token>, X-Correlation-ID: <uuid>

2. Middleware: CorrelationMiddleware
   - If X-Correlation-ID header exists → use it
   - Else → generate uuid4
   - Store in request.state.correlation_id

3. Middleware: TimingMiddleware
   - Record start time

4. Route handler: fhir_proxy()
   - Extract bearer token from Authorization header
   - If missing → return 401 (AUTH_001)

5. PCM Token (pcm_client.get_token()):
   - Check cache: if cached_token exists AND not expired → use it
   - Else:
     a. Build client_assertion JWT:
        - header: {"alg": "ES256", "typ": "JWT"}
        - payload: {"iss": <adapter_client_id>, "sub": <adapter_client_id>, 
                    "aud": <pcm_token_url>, "exp": now+60, "iat": now, "jti": uuid4}
        - Sign with DS_ADAPTER_PCM_CLIENT_KEY
     b. POST pcm.base_url + pcm.token_endpoint
        Content-Type: application/x-www-form-urlencoded
        Body: grant_type=client_credentials
              &client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer
              &client_assertion=<signed_jwt>
              &scope=<pcm.token_scope>
     c. Parse response: {access_token, token_type, expires_in}
     d. Cache: store access_token with expires_at = now + expires_in

6. Introspection (pcm_client.introspect()):
   - POST pcm.base_url + pcm.introspect_endpoint
     Headers: Authorization: Bearer <adapter_access_token>
     Content-Type: application/x-www-form-urlencoded
     Body: token=<opaque_token_from_sp>
   - Parse response → IntrospectionResponse
   - If active == false → return 401 (AUTH_002)
   - Extract: patient, scope, consent_id, baskets, access_type, sp_organization_id, cnf

7. CNF Comparison:
   - If cnf.x5t#S256 exists AND client cert available:
     - Compute SHA-256 of client cert DER
     - Compare with cnf.x5t#S256
     - If mismatch → LOG WARNING (do NOT block)

8. ID Replacement (id_replacement.resolve()):
   - POST id_replacement.base_url + id_replacement.endpoint
     Content-Type: application/json
     Authorization: <from DS_ADAPTER_ID_REPLACEMENT_AUTH>
     Body: {"identifier": {"system": "http://fhir.health.gov.il/identifier/il-national-id", "value": "<patient_from_introspection>"}}
   - On success: extract patient_id
   - On 404: return 404 (ID_002)
   - On timeout/error: retry up to id_replacement.retries times with backoff
   - All retries failed: return 502 (ID_001)

9. Mint Internal JWT (jwt_service.mint()):
   - Build payload:
     {
       "iss": config.jwt.issuer,  // "ds-adapter"
       "sub": local_patient_id,
       "aud": config.fhir_server.base_url,
       "exp": now + config.jwt.expiry_seconds,
       "iat": now,
       "consent_id": introspection.consent_id,
       "scope": introspection.scope,
       "patient": local_patient_id,
       "baskets": introspection.baskets,
       "access_type": introspection.access_type,
       "sp_organization_id": introspection.sp_organization_id,
       "correlation_id": correlation_id
     }
   - Sign with ES256 using DS_ADAPTER_JWT_SIGNING_KEY
   - Return signed JWT string

10. Inject Security Parameter:
    - If request method is GET or (POST and path ends with _search):
      - Append to query string: &_security:not=http://fhir.health.gov.il/cs/il-core-main-security-label|V
    - Else: do not modify query

11. Forward to FHIR (fhir.client.forward()):
    - Build URL: config.fhir_server.base_url + original_path + modified_query
    - Method: same as original request
    - Headers: Authorization: Bearer <internal_jwt>, X-Correlation-ID: <correlation_id>
    - Body: original request body (if POST/PUT/PATCH)
    - Timeout: config.fhir_server.timeout_seconds
    - On timeout: return 504 (FHIR_002)
    - On connection error: return 502 (FHIR_001)

12. Verify Response (fhir.verification.verify()):
    - If config.verification.enabled == false → skip
    - Parse response body as JSON
    - If resourceType == "Bundle":
      - For each entry in bundle.entry:
        - Check entry.resource.meta.security (array)
        - For each security coding: build "system|code" string
        - If matches any in config.verification.forbidden_labels → FAIL
    - If resourceType != "Bundle" (single resource):
      - Check resource.meta.security same way
    - On FAIL:
      - Log CRITICAL: "Forbidden security label detected in FHIR response"
      - Write audit with severity=critical
      - Return 400 with generic OperationOutcome (NO details about which label)
    - On PASS: continue

13. Audit (audit.service.record()):
    - Build AuditRecord with all fields
    - Dispatch to enabled targets (async, non-blocking)
    - Audit failure must NOT fail the request

14. Return response to caller:
    - Status: FHIR server's status code
    - Headers: X-Correlation-ID, Content-Type: application/fhir+json
    - Body: FHIR response body
```

### 5.2 Error Handling — כל שגיאה

| שלב | תנאי כשל | Error Code | HTTP | פעולה |
|------|-----------|------------|------|-------|
| 4 | Bearer token חסר/לא תקין | AUTH_001 | 401 | Return immediately |
| 5 | PCM unreachable | PCM_001 | 502 | Return immediately |
| 5 | PCM returns error | PCM_002 | 401 | Return immediately |
| 6 | active=false | AUTH_002 | 401 | Return immediately |
| 6 | token expired | AUTH_003 | 401 | Return immediately |
| 8 | Patient not found (404) | ID_002 | 404 | Return immediately |
| 8 | Service unavailable (after retries) | ID_001 | 502 | Return immediately |
| 11 | FHIR timeout | FHIR_002 | 504 | Return immediately |
| 11 | FHIR connection error | FHIR_001 | 502 | Return immediately |
| 12 | Forbidden label found | — | 400 | Generic OperationOutcome |
| Any | Unexpected exception | GEN_001 | 500 | Log + return |
| Startup | Config invalid | CFG_001 | 500 | Fail to start |

---

## 6. API Endpoints

### 6.1 FHIR Proxy (External — via Gateway)

```
{METHOD} /fhir/{path:path}

Methods: GET, POST, PUT, DELETE, PATCH
Auth: Bearer <opaque_token> (required)
Headers:
  - Authorization: Bearer <token> (required)
  - X-Correlation-ID: <uuid> (optional)
  - Content-Type: application/fhir+json (for POST/PUT/PATCH)

Response: Whatever FHIR Server returns, or OperationOutcome on error
Response Headers: X-Correlation-ID (always)
```

### 6.2 Health (Internal)

```
GET /health
Response 200: {"status": "ok"}
```

### 6.3 Readiness (Internal)

```
GET /ready
Response 200: {"status": "ready", "fhir_server": "ok", "pcm": "ok"}
Response 503: {"status": "not_ready", "fhir_server": "error", "pcm": "ok"}

Logic:
  - Try HEAD request to fhir_server.base_url (timeout 5s)
  - Try HEAD request to pcm.base_url (timeout 5s)
  - If both succeed → 200
  - If any fails → 503
```

### 6.4 Metrics (Internal)

```
GET /metrics
Response 200: Prometheus text format

Metrics exposed:
  - ds_adapter_requests_total{method, status, path}
  - ds_adapter_request_duration_seconds{method, path}
  - ds_adapter_pcm_introspection_duration_seconds
  - ds_adapter_id_replacement_duration_seconds
  - ds_adapter_fhir_forward_duration_seconds
  - ds_adapter_errors_total{error_code}
```

---

## 7. Error Response Format

כל שגיאה מוחזרת כ-FHIR OperationOutcome:

```json
{
  "resourceType": "OperationOutcome",
  "issue": [
    {
      "severity": "error",
      "code": "<issue_code>",
      "details": {
        "coding": [
          {
            "system": "http://ds-adapter/error-codes",
            "code": "<ERROR_CODE>",
            "display": "<human readable>"
          }
        ]
      },
      "diagnostics": "<safe message, no internal details>"
    }
  ]
}
```

### Error Catalog

| Code | HTTP | Issue Code | Display | Diagnostics |
|------|------|------------|---------|-------------|
| AUTH_001 | 401 | login | Missing or invalid Bearer token | Authorization header is missing or malformed |
| AUTH_002 | 401 | login | Token introspection failed | The provided access token is not active |
| AUTH_003 | 401 | login | Token expired | The provided access token has expired |
| AUTH_004 | 403 | forbidden | Consent not valid | The consent does not authorize access to the requested resource |
| AUTH_005 | 403 | forbidden | Certificate mismatch | Client certificate does not match token binding |
| ID_001 | 502 | exception | ID service unavailable | Patient identity resolution service is temporarily unavailable |
| ID_002 | 404 | not-found | Patient not found | No local patient record found for the given identifier |
| FHIR_001 | 502 | exception | FHIR Server unavailable | The internal FHIR server is temporarily unavailable |
| FHIR_002 | 504 | timeout | FHIR Server timeout | The internal FHIR server did not respond in time |
| PCM_001 | 502 | exception | PCM unreachable | The consent management system is temporarily unavailable |
| PCM_002 | 401 | login | PCM token acquisition failed | Failed to authenticate with the consent management system |
| CFG_001 | 500 | exception | Configuration error | Service configuration is invalid |
| GEN_001 | 500 | exception | Internal error | An unexpected error occurred |

---

## 8. Audit — מפרט מלא

### 8.1 כללים
- **כל בקשה** נרשמת — גם הצלחות וגם כשלונות
- Response body **מושבת** כברירת מחדל (config: `audit.include_response`)
- Audit failure **לא** מכשיל את הבקשה
- `patient_id` נשמר **masked** (4 ספרות אחרונות בלבד)

### 8.2 Audit Record Fields

```json
{
  "timestamp": "2025-01-15T10:30:00.000Z",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "source_ip": "10.0.1.50",
  "method": "GET",
  "path": "/fhir/Observation",
  "fhir_scope": "patient/Observation.rs",
  "patient_id": "****0018",
  "sp_organization_id": "org-hospital-a",
  "consent_id": "consent-12345",
  "response_status": 200,
  "response_time_ms": 145.3,
  "error": null
}
```

### 8.3 Targets

**File**: Append JSON lines to file. Daily rotation. Keep max_files.
**Kafka**: Produce JSON message to topic. Async. Fire-and-forget.
**Syslog**: Send RFC 5424 message. UDP or TCP. Facility LOCAL0.

---

## 9. Observability — OpenTelemetry

### 9.1 Spans (Traces)

| Span | Parent | Attributes |
|------|--------|------------|
| `http.request` | root | method, path, status_code, correlation_id |
| `pcm.token_acquire` | http.request | cached (bool), pcm_url |
| `pcm.introspect` | http.request | active (bool), patient_id |
| `id.replacement` | http.request | patient_id, attempt_count |
| `jwt.mint` | http.request | patient_id, expiry |
| `fhir.forward` | http.request | url, method, status_code |
| `fhir.verify` | http.request | passed (bool) |

### 9.2 Metrics

| Name | Type | Labels | Description |
|------|------|--------|-------------|
| ds_adapter_requests_total | Counter | method, status, path | Total requests |
| ds_adapter_request_duration_seconds | Histogram | method, path | E2E latency |
| ds_adapter_pcm_introspection_duration_seconds | Histogram | — | PCM introspection time |
| ds_adapter_id_replacement_duration_seconds | Histogram | — | ID resolution time |
| ds_adapter_fhir_forward_duration_seconds | Histogram | — | FHIR forward time |
| ds_adapter_errors_total | Counter | error_code | Errors by code |
| ds_adapter_token_cache_hits_total | Counter | — | Token cache hits |
| ds_adapter_token_cache_misses_total | Counter | — | Token cache misses |

---

## 10. Logging

### 10.1 Format

```json
{"timestamp": "2025-01-15T10:30:00.000Z", "level": "info", "correlation_id": "...", "message": "...", "context": {...}}
```

### 10.2 What to Log

| Level | Events |
|-------|--------|
| ERROR | PCM unreachable, FHIR timeout, unexpected exceptions |
| WARNING | cnf mismatch, audit target failure, retry attempt |
| INFO | Request received, introspection success, JWT minted, response sent |
| DEBUG | Request body, full introspection response, FHIR response body, full config |

### 10.3 Output Routing
- INFO + DEBUG → stdout
- WARNING + ERROR → stderr

---

## 11. mTLS — שני מצבים

### Mode 1: `pcm.mtls_client: true`
```python
# Create httpx client with mutual TLS
client = httpx.AsyncClient(
    cert=(pcm_client_cert_path, pcm_client_key_path),
    verify=pcm_ca_cert_path,
    timeout=10.0
)
```

### Mode 2: `pcm.mtls_client: false`
```python
# Plain HTTP/HTTPS — external layer handles mTLS
client = httpx.AsyncClient(timeout=10.0)
```

---

## 12. Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config.yaml .

RUN useradd -r -s /bin/false appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 13. docker-compose.yaml (Local Dev)

```yaml
version: "3.8"
services:
  ds-adapter:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DS_ADAPTER_PCM_BASE_URL=https://mock-pcm:3000
      - DS_ADAPTER_FHIR_SERVER_BASE_URL=http://mock-fhir:8080
      - DS_ADAPTER_PCM_CLIENT_CERT=/certs/client.crt
      - DS_ADAPTER_PCM_CLIENT_KEY=/certs/client.key
      - DS_ADAPTER_PCM_CA_CERT=/certs/ca.crt
      - DS_ADAPTER_JWT_SIGNING_KEY=/certs/jwt-signing.key
    volumes:
      - ./certs:/certs:ro
      - ./config.yaml:/app/config.yaml:ro
    depends_on:
      - mock-pcm
      - mock-fhir

  mock-pcm:
    image: mockserver/mockserver:latest
    ports:
      - "3000:1080"

  mock-fhir:
    image: mockserver/mockserver:latest
    ports:
      - "8080:1080"
```

---

## 14. Testing Strategy

### 14.1 Unit Tests — per module

| File | Tests |
|------|-------|
| test_pcm_client.py | get_token success, get_token PCM error, token cache hit, token cache expired, introspect active, introspect inactive, introspect PCM error |
| test_jwt_service.py | mint correct claims, mint correct signature (verify with public key), mint expiry correct |
| test_id_replacement.py | resolve success, resolve 404, resolve timeout+retry, resolve all retries fail |
| test_verification.py | bundle no labels → pass, bundle with V → fail, single resource with V → fail, disabled → skip, empty bundle → pass |
| test_config.py | load yaml, env override, missing required field → error |
| test_error_handlers.py | each error code → correct OperationOutcome JSON |
| test_correlation.py | extract from header, generate when missing, propagate to response |

### 14.2 Integration Tests — full flow with mocks

| File | Scenario |
|------|----------|
| test_happy_path.py | Full flow → 200 + Bundle |
| test_auth_failures.py | No token → 401, inactive → 401, PCM down → 502 |
| test_id_failures.py | Patient not found → 404, service down → 502 |
| test_fhir_failures.py | FHIR timeout → 504, FHIR error → 502 |
| test_verification_failures.py | Forbidden label → 400 |

### 14.3 conftest.py Fixtures

```python
# Key fixtures needed:
# - app: FastAPI test app with config overrides
# - client: httpx.AsyncClient(app=app)
# - mock_pcm: respx mock for PCM endpoints
# - mock_fhir: respx mock for FHIR server
# - mock_id_service: respx mock for ID replacement
# - sample_introspection_response: valid introspection JSON
# - sample_fhir_bundle: valid FHIR Bundle JSON
# - sample_fhir_bundle_with_v_label: Bundle with forbidden label
# - es256_keypair: (private_key, public_key) for JWT testing
```

---

## 15. Graceful Shutdown

1. Receive SIGTERM
2. Stop accepting new connections (uvicorn handles this)
3. Wait for in-flight requests (up to `server.shutdown_timeout_seconds`)
4. Flush audit file buffer
5. Close Kafka producer
6. Close httpx clients
7. Exit 0

---

## 16. ID Replacement Contract (Template for Organizations)

Organizations implement this API. The adapter calls it.

```
POST /api/v1/resolve
Content-Type: application/json
Authorization: <org-specific>

Request:
{
  "identifier": {
    "system": "http://fhir.health.gov.il/identifier/il-national-id",
    "value": "000000018"
  }
}

Response 200:
{
  "patient_id": "12345",
  "resource_reference": "Patient/12345"
}

Response 404:
{
  "error": "patient_not_found",
  "message": "No local patient record found for given identifier"
}

Response 503:
{
  "error": "service_unavailable",
  "message": "ID resolution service is temporarily unavailable"
}
```

---

## 17. Security Notes

- **No secrets in code or config files** — all from env vars
- **No stack traces in responses** — only safe diagnostics messages
- **Patient ID masked in audit** — show only last 4 digits
- **Verification is defense-in-depth** — even if FHIR Server filters correctly, adapter double-checks
- **cnf mismatch is WARNING only** — spec says non-blocking
- **Audit cannot fail the request** — wrap in try/except, log warning on failure
