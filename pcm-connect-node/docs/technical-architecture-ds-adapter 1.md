# מסמך ארכיטקטורה ודרישות טכניות - Data Source Adapter

## 1. סקירה כללית

### 1.1 מטרת המערכת
ה-Data Source Adapter (להלן: "האדפטר") הוא שירות stateless המשמש כ-Policy Enforcement Point (PEP) עבור מקור מידע (Data Source) במערכת ניוד מידע רפואי (HDP). האדפטר מקבל בקשות ממקבלי מידע (Service Providers), מאמת את הטוקן מול המהרש"ג (PCM), ממפה זהות מטופל למזהה מקומי, ומנפיק JWT פנימי לשרת ה-FHIR של הארגון.

### 1.2 עקרונות תכנון
- **Stateless** — אין שמירת state בין בקשות; כל בקשה עצמאית
- **Configuration-driven** — כל התנהגות ניתנת לשינוי דרך קונפיגורציה
- **Instance per organization** — כל ארגון מריץ instance משלו
- **Contract-first** — ממשקים מוגדרים ב-OpenAPI/Swagger
- **Observable** — audit, logging, metrics מובנים

### 1.3 טכנולוגיות
| רכיב | טכנולוגיה |
|-------|-----------|
| שפה | Python 3.11+ |
| Framework | FastAPI |
| API Docs | Swagger/OpenAPI (מובנה ב-FastAPI) |
| Container | Docker |
| JWT | ES256 (ECDSA P-256) |
| Audit Broker | Kafka |
| Config | YAML + Environment Variables override |
| Observability | OpenTelemetry (traces, metrics, logs) |

---

## 2. ארכיטקטורה

### 2.1 דיאגרמת רכיבים

```
+------------------+       +-------------------+       +------------------+
|   API Gateway    |       |   Data Source     |       |   FHIR Server    |
|   / Istio        |------>|   Adapter         |------>|   (קיים)         |
|   (mTLS אופציונלי)|       |   (FastAPI)       |       |                  |
+------------------+       +-------------------+       +------------------+
                                    |
                                    | Introspection
                                    v
                           +-------------------+
                           |   PCM Core        |
                           |   (מהרש"ג)        |
                           +-------------------+
                                    
                           +-------------------+
                           |  ID Replacement   |
                           |  Service (חיצוני) |
                           +-------------------+
```

### 2.2 זרימת בקשה (Request Flow)

1. **קבלת בקשה** — Gateway מעביר בקשה עם Bearer token (opaque)
2. **Correlation ID** — אם קיים header `X-Correlation-ID` משתמשים בו, אחרת נוצר UUID חדש
3. **Token Introspection** — האדפטר מבקש token חדש מה-PCM (client_credentials + private_key_jwt), ואז קורא ל-`/introspect` עם הטוקן של ה-SP
4. **ID Replacement** — קריאה לשירות חיצוני להמרת מזהה לאומי למזהה מטופל מקומי
5. **JWT Minting** — יצירת JWT פנימי חתום ב-ES256 עם claims מהמפרט
6. **Forward to FHIR** — העברת הבקשה ל-FHIR Server עם ה-JWT הפנימי
7. **Audit** — רישום audit record
8. **Response** — החזרת תשובת ה-FHIR Server ל-caller

---

## 3. קונפיגורציה

### 3.1 מנגנון טעינה
- **מקור ראשי**: קובץ YAML (`config.yaml`)
- **Override**: Environment variables גוברים על ערכי YAML
- **Convention**: env var בפורמט `DS_ADAPTER_<SECTION>_<KEY>` (uppercase, underscore separator)
- **דוגמה**: `DS_ADAPTER_PCM_BASE_URL` גובר על `pcm.base_url` ב-YAML

### 3.2 מבנה קונפיגורציה

```yaml
# --- Server ---
server:
  host: "0.0.0.0"
  port: 8000
  shutdown_timeout_seconds: 30

# --- PCM Integration ---
pcm:
  base_url: "https://pcm-core:3000"
  fhir_base_url: "https://pcm-core:3000/r4"
  token_endpoint: "/token"
  introspect_endpoint: "/introspect"
  mtls_client: true  # true = adapter מבצע mTLS, false = plain HTTP (gateway/istio מטפל)
  
# --- FHIR Server ---
fhir_server:
  base_url: "https://fhir-internal:8080"
  protocol: "https"  # http | https
  timeout_seconds: 30
  
# --- ID Replacement ---
id_replacement:
  base_url: "http://id-service:9000"
  endpoint: "/api/v1/resolve"
  timeout_seconds: 1
  retries: 3
  retry_backoff_seconds: 0.5

# --- JWT (Internal Token) ---
jwt:
  algorithm: "ES256"
  issuer: "ds-adapter"
  expiry_seconds: 300

# --- Audit ---
audit:
  enabled: true
  format: "json"  # json | cef
  include_response: false  # disabled by default
  targets:
    syslog:
      enabled: false
      host: "localhost"
      port: 514
      protocol: "udp"  # udp | tcp
    file:
      enabled: true
      path: "/var/log/adapter/audit.log"
      rotation: "daily"
      max_files: 30
    kafka:
      enabled: false
      brokers: "kafka:9092"
      topic: "ds-adapter-audit"

# --- Logging ---
logging:
  level: "info"  # debug | info | warning | error
  format: "json"
  # In debug: request body, fhir scope, and response are logged
  
# --- Secrets (all from environment variables) ---
# DS_ADAPTER_PCM_CLIENT_CERT - PEM encoded client certificate
# DS_ADAPTER_PCM_CLIENT_KEY - PEM encoded private key
# DS_ADAPTER_PCM_CA_CERT - PEM encoded CA certificate
# DS_ADAPTER_JWT_SIGNING_KEY - PEM encoded ES256 private key
# DS_ADAPTER_ID_REPLACEMENT_AUTH - Basic auth credentials (user:pass)
```

### 3.3 Secrets
כל ה-secrets נטענים מ-environment variables.

> **חובה**: צוות DevOps/System חייב להשתמש ב-**HashiCorp Vault**, **AWS Secrets Manager**, **Azure Key Vault** או פתרון secrets management מקביל כדי למפות את ה-secrets ל-environment variables. אסור להכניס secrets ישירות ל-deployment manifests, Docker Compose files, או CI/CD pipelines.

| Variable | תיאור |
|----------|--------|
| `DS_ADAPTER_PCM_CLIENT_CERT` | Client certificate (PEM) עבור mTLS מול PCM |
| `DS_ADAPTER_PCM_CLIENT_KEY` | Private key (PEM) עבור mTLS מול PCM |
| `DS_ADAPTER_PCM_CA_CERT` | CA certificate (PEM) לאימות PCM |
| `DS_ADAPTER_JWT_SIGNING_KEY` | ES256 private key לחתימת JWT פנימי |
| `DS_ADAPTER_JWT_VERIFY_KEY` | ES256 public key (אופציונלי, לצורך verification) |

---

## 4. חיבור ל-PCM (מהרש"ג)

### 4.1 שני מצבי mTLS

#### מצב 1: `mtls_client: true`
האדפטר עצמו מבצע mTLS מול ה-PCM:
- טוען client certificate ו-private key מ-env vars
- יוצר HTTPS session עם mutual authentication
- מתאים ל-deployment ללא service mesh

#### מצב 2: `mtls_client: false`
ה-mTLS מבוצע ע"י שכבה חיצונית (API Gateway / Istio sidecar):
- האדפטר שולח בקשות HTTP רגילות
- ה-sidecar/gateway מוסיף את ה-client certificate
- מתאים ל-Kubernetes עם Istio

### 4.2 Token Acquisition
בכל בקשה, האדפטר מבקש token חדש מה-PCM:
- **Method**: POST `/token`
- **Auth**: `private_key_jwt` (client_assertion חתום ב-ES256)
- **Grant**: `client_credentials`
- **Resource**: כתובת ה-endpoint של האדפטר (RFC 8707)

### 4.3 Introspection
- **Method**: POST `/introspect`
- **Auth**: Bearer token (שהתקבל ב-4.2)
- **Body**: `token=<opaque_token_from_SP>`
- **Response**: Claims כולל `active`, `scope`, `patient`, `fhirContext`, `cnf`
- **No caching** — כל בקשה מבצעת introspection חדש

---

## 5. ID Replacement (המרת מזהה)

### 5.1 עיקרון
כל ארגון מממש שירות ID Replacement משלו בהתאם לסטנדרטים הפנימיים שלו. האדפטר מגדיר רק את ה-**contract** (חוזה הממשק).

### 5.2 Contract Definition

#### Request
```
POST {id_replacement.base_url}{id_replacement.endpoint}
Content-Type: application/json
Authorization: <configured per organization>

{
  "national_id": {
    "system": "http://fhir.health.gov.il/identifier/il-national-id",
    "value": "000000018"
  }
}
```

#### Response - Success (FHIR Patient Reference)
```json
{
  "patient_id": "12345",
  "resource_reference": "Patient/12345"
}
```

#### Response - Not Found
```json
{
  "error": "patient_not_found",
  "message": "No local patient record found for given identifier"
}
```
HTTP Status: `404`

#### Response - Error
```json
{
  "error": "service_unavailable",
  "message": "ID resolution service is temporarily unavailable"
}
```
HTTP Status: `503`

### 5.3 Authentication
ה-authentication לשירות ה-ID Replacement מוגדר ע"י הארגון המממש. האדפטר תומך בהעברת credentials מוגדרים ב-config (header value מ-env var).

### 5.4 Timeout & Retry
- **Timeout**: קונפיגורבילי, ברירת מחדל 1 שנייה
- **Retries**: קונפיגורבילי, ברירת מחדל 3 ניסיונות
- **Backoff**: קונפיגורבילי, ברירת מחדל 0.5 שניות בין ניסיונות
- **Failure**: אם כל הניסיונות נכשלים — מחזיר FHIR OperationOutcome עם error

---

## 6. JWT פנימי (Local Token)

### 6.1 מבנה Claims
בהתאם למפרט המהרש"ג, ה-JWT הפנימי מכיל:

```json
{
  "iss": "ds-adapter",
  "sub": "<local_patient_id>",
  "aud": "<fhir_server_base_url>",
  "exp": 1234567890,
  "iat": 1234567590,
  "consent_id": "<consent_identifier>",
  "scope": "patient/Observation.rs patient/Condition.rs",
  "patient": "<local_patient_id>",
  "baskets": [
    {
      "code": "laboratoryTests",
      "system": "http://fhir.health.gov.il/cs/hdp-information-buckets",
      "historical_depth": "2024-01-01"
    }
  ],
  "access_type": "continuous",
  "sp_organization_id": "<requesting_sp_org_id>",
  "correlation_id": "<correlation_id>"
}
```

### 6.2 חתימה
- **Algorithm**: ES256 (ECDSA P-256)
- **Key**: Private key מ-env var `DS_ADAPTER_JWT_SIGNING_KEY`
- **Expiry**: קונפיגורבילי, ברירת מחדל 300 שניות

---

## 7. Audit Framework

### 7.1 עקרונות
- **כל בקשה נרשמת** — ללא יוצא מן הכלל
- **Response מושבת כברירת מחדל** — ניתן להפעלה דרך config
- **Multi-target** — syslog, file, Kafka (כל אחד enabled/disabled בנפרד)
- **Format** — JSON או CEF (קונפיגורבילי)

### 7.2 שדות Audit Record

| שדה | תיאור | חובה |
|-----|--------|------|
| `timestamp` | ISO 8601 | כן |
| `correlation_id` | מזהה ייחודי לבקשה | כן |
| `source_ip` | כתובת IP של הפונה | כן |
| `method` | HTTP method | כן |
| `path` | Request path | כן |
| `fhir_scope` | Scope מה-introspection | כן |
| `patient_id` | מזהה מטופל (masked) | כן |
| `sp_organization_id` | מזהה מקבל המידע | כן |
| `consent_id` | מזהה הסכמה | כן |
| `response_status` | HTTP status code | כן |
| `response_time_ms` | זמן תגובה במילישניות | כן |
| `response_body` | גוף התשובה | **לא (disabled by default)** |
| `error` | פרטי שגיאה (אם רלוונטי) | מותנה |

### 7.3 Targets

#### Syslog
- Protocol: UDP/TCP (קונפיגורבילי)
- Format: RFC 5424
- Facility: LOCAL0

#### File
- Path: קונפיגורבילי
- Rotation: יומי
- Retention: 30 קבצים (קונפיגורבילי)

#### Kafka
- Brokers: קונפיגורבילי
- Topic: קונפיגורבילי
- Serialization: JSON
- Delivery: async (fire-and-forget, לא חוסם את הבקשה)

---

## 8. Logging

### 8.1 רמות
| רמה | תוכן |
|------|-------|
| `ERROR` | שגיאות שמונעות עיבוד בקשה |
| `WARNING` | מצבים חריגים שלא מונעים עיבוד (למשל cnf mismatch) |
| `INFO` | אירועים עסקיים (בקשה התקבלה, introspection הצליח, JWT נוצר) |
| `DEBUG` | **כולל**: request body, fhir scope, response body |

### 8.2 פורמט ויעדים
- JSON structured
- כולל: `timestamp`, `level`, `correlation_id`, `message`, `context`
- **stdout** — כל הלוגים ברמת INFO ומטה (INFO, DEBUG) נכתבים ל-stdout
- **stderr** — כל הלוגים ברמת WARNING ומעלה (WARNING, ERROR) נכתבים ל-stderr
- תואם ל-container logging best practices (Docker/K8s log collectors)

### 8.3 הבדל בין Audit ל-Logging
- **Audit** = רשומה רשמית לצורך ציות רגולטורי (כל בקשה, שדות קבועים)
- **Logging** = מידע תפעולי לצורך debug ו-monitoring (רמות, גמישות)

---

## 9. Error Handling

### 9.1 עקרונות
- כל שגיאה מוחזרת כ-**FHIR OperationOutcome**
- שגיאות מוגדרות מראש ומתועדות ב-Swagger
- אין חשיפת מידע פנימי (stack traces, internal paths)
- כל שגיאה כוללת `correlation_id` ב-response header

### 9.2 קטלוג שגיאות

| קוד | HTTP Status | Issue Code | תיאור |
|-----|-------------|------------|--------|
| `AUTH_001` | 401 | `login` | Missing or invalid Bearer token |
| `AUTH_002` | 401 | `login` | Token introspection failed (inactive) |
| `AUTH_003` | 401 | `login` | Token expired |
| `AUTH_004` | 403 | `forbidden` | Consent not valid for requested resource |
| `AUTH_005` | 403 | `forbidden` | mTLS certificate mismatch (blocking mode) |
| `ID_001` | 502 | `exception` | ID Replacement service unavailable |
| `ID_002` | 404 | `not-found` | Patient not found in local system |
| `FHIR_001` | 502 | `exception` | FHIR Server unavailable |
| `FHIR_002` | 504 | `timeout` | FHIR Server timeout |
| `PCM_001` | 502 | `exception` | PCM unreachable |
| `PCM_002` | 401 | `login` | Failed to acquire PCM token |
| `CFG_001` | 500 | `exception` | Configuration error |
| `GEN_001` | 500 | `exception` | Unexpected internal error |

### 9.3 Response Format
```json
{
  "resourceType": "OperationOutcome",
  "issue": [
    {
      "severity": "error",
      "code": "login",
      "details": {
        "coding": [
          {
            "system": "http://ds-adapter/error-codes",
            "code": "AUTH_002",
            "display": "Token introspection returned inactive"
          }
        ]
      },
      "diagnostics": "The provided access token is not active"
    }
  ]
}
```

---

## 10. API Specification (Swagger)

### 10.1 External API (דרך Gateway)

#### {METHOD} /fhir/{resource_type}/{id?}
- **תיאור**: Proxy לשרת FHIR פנימי — תומך בכל פעולות FHIR REST
- **Methods**: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`
- **Auth**: Bearer token (opaque, מונפק ע"י PCM)
- **Headers**: `X-Correlation-ID` (אופציונלי), `Content-Type: application/fhir+json`
- **Response**: FHIR Resource / Bundle / OperationOutcome (בהתאם לפעולה)
- **Errors**: FHIR OperationOutcome

> **הערה**: ה-Swagger מתעד את ה-adapter endpoints (health, ready, metrics) ואת ה-ID Replacement contract. בקשות FHIR עוברות כ-proxy שקוף — האדפטר לא מפרש את תוכן הבקשה אלא רק מאמת הרשאה ומעביר ל-FHIR Server.

### 10.2 ID Replacement API (Template לארגונים)

#### POST /api/v1/resolve
- **תיאור**: המרת מזהה לאומי למזהה מטופל מקומי
- **Auth**: מוגדר ע"י הארגון
- **Request Body**: `{ "national_id": { "system": "...", "value": "..." } }`
- **Response**: `{ "patient_id": "...", "system": "...", "resource_reference": "..." }`
- **Errors**: `404` (not found), `503` (unavailable)

### 10.3 Internal APIs

#### GET /health
- **תיאור**: Liveness probe
- **Response**: `{ "status": "ok" }`

#### GET /ready
- **תיאור**: Readiness probe (בודק חיבור ל-FHIR Server ול-PCM)
- **Response**: `{ "status": "ready", "fhir_server": "ok", "pcm": "ok" }`

#### GET /metrics
- **תיאור**: Prometheus metrics
- **Response**: Prometheus text format

---

## 11. OpenTelemetry

### 11.1 עקרונות
האדפטר משתמש ב-OpenTelemetry (OTel) כסטנדרט observability:
- **Traces** — כל בקשה יוצרת span ראשי עם child spans עבור: introspection, ID replacement, FHIR forward
- **Metrics** — request count, latency histogram, error rate, active connections
- **Logs** — correlation בין logs ל-traces דרך trace_id ו-span_id

### 11.2 קונפיגורציה

```yaml
# --- OpenTelemetry ---
otel:
  enabled: true
  exporter: "otlp"  # otlp | jaeger | zipkin | console
  endpoint: "http://otel-collector:4317"
  service_name: "ds-adapter"
  sample_rate: 1.0  # 0.0 to 1.0
```

### 11.3 Spans
| Span Name | Parent | תיאור |
|-----------|--------|--------|
| `http.request` | root | בקשה נכנסת |
| `pcm.token_acquire` | http.request | בקשת token מ-PCM |
| `pcm.introspect` | http.request | Introspection מול PCM |
| `id.replacement` | http.request | קריאה ל-ID Replacement |
| `jwt.mint` | http.request | יצירת JWT פנימי |
| `fhir.forward` | http.request | העברה ל-FHIR Server |

### 11.4 Metrics (Prometheus-compatible)
| Metric | Type | תיאור |
|--------|------|--------|
| `ds_adapter_requests_total` | Counter | סה"כ בקשות (labels: method, status, path) |
| `ds_adapter_request_duration_seconds` | Histogram | זמן תגובה |
| `ds_adapter_pcm_introspection_duration_seconds` | Histogram | זמן introspection |
| `ds_adapter_id_replacement_duration_seconds` | Histogram | זמן ID replacement |
| `ds_adapter_fhir_forward_duration_seconds` | Histogram | זמן FHIR forward |
| `ds_adapter_errors_total` | Counter | שגיאות (labels: error_code) |

---

## 12. Deployment

### 12.1 דרישות מערכת מומלצות

#### Minimum (Development/Testing)
| משאב | ערך |
|-------|-----|
| CPU Request | 250m |
| CPU Limit | 500m |
| Memory Request | 256Mi |
| Memory Limit | 512Mi |
| Storage | SSD (לא נדרש persistent) |

#### Production (Recommended)
| משאב | ערך |
|-------|-----|
| CPU Request | 500m |
| CPU Limit | 2000m |
| Memory Request | 512Mi |
| Memory Limit | 1Gi |
| Storage | NVMe/SSD (עבור audit file logging) |
| Replicas | 2+ (HA) |

#### דרישות תשתית
- **Disk**: SSD/NVMe מומלץ — נדרש עבור audit file writes עם latency נמוך
- **Network**: Low latency לשרת FHIR ול-PCM (< 5ms intra-cluster)
- **OS**: Linux (container-optimized)

### 12.2 Docker
- Container יחיד (adapter בלבד)
- FHIR Server הוא שירות חיצוני קיים
- Base image: `python:3.11-slim`
- Non-root user
- Health check מובנה

### 12.3 Dockerfile (מבנה)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY config.yaml .
USER nobody
EXPOSE 8000
HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 12.4 Graceful Shutdown
- מפסיק לקבל בקשות חדשות
- ממתין לסיום בקשות in-flight (timeout קונפיגורבילי, ברירת מחדל 30 שניות)
- יוצא עם exit code 0

### 12.5 SLA
- **Availability**: 99.98%
- **Response Time**: תלוי ב-FHIR Server + PCM introspection

---

## 13. Testing

### 13.1 Unit Tests
- כל module נבדק בנפרד
- Mock ל-PCM, FHIR Server, ID Replacement
- Coverage target: 80%+

### 13.2 Integration Tests
- Mock PCM server (מחזיר introspection responses)
- Mock FHIR server (מחזיר FHIR bundles)
- Mock ID Replacement service
- בדיקת flow מלא end-to-end עם mocks
- בדיקת error scenarios (timeout, 401, 404)

### 13.3 Contract Tests
- OpenAPI validation — responses תואמים ל-schema
- FHIR validation — OperationOutcome תקין

---

## 14. מבנה פרויקט

```
ds-adapter/
├── src/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py         # Configuration loading (YAML + env override)
│   │   └── models.py           # Pydantic config models
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py           # FHIR proxy routes
│   │   └── dependencies.py     # FastAPI dependencies (auth, correlation)
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── pcm_client.py       # PCM token + introspection
│   │   ├── jwt_service.py      # Internal JWT minting (ES256)
│   │   └── mtls.py             # mTLS session management
│   ├── identity/
│   │   ├── __init__.py
│   │   └── id_replacement.py   # ID Replacement client
│   ├── fhir/
│   │   ├── __init__.py
│   │   └── client.py           # FHIR Server HTTP client
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── service.py          # Audit orchestrator
│   │   ├── targets/
│   │   │   ├── syslog.py
│   │   │   ├── file.py
│   │   │   └── kafka.py
│   │   └── formatters/
│   │       ├── json_fmt.py
│   │       └── cef_fmt.py
│   ├── errors/
│   │   ├── __init__.py
│   │   ├── catalog.py          # Error code definitions
│   │   ├── handlers.py         # Global exception handlers
│   │   └── models.py           # OperationOutcome builder
│   ├── logging/
│   │   ├── __init__.py
│   │   └── setup.py            # Structured logging config (stdout/stderr)
│   ├── otel/
│   │   ├── __init__.py
│   │   └── setup.py            # OpenTelemetry initialization (traces, metrics)
│   └── middleware/
│       ├── __init__.py
│       ├── correlation.py      # X-Correlation-ID middleware
│       ├── audit_middleware.py  # Request/response audit capture
│       └── timing.py           # Response time measurement
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── config.yaml
├── Dockerfile
├── requirements.txt
├── docker-compose.yaml         # Local dev environment
└── README.md
```
