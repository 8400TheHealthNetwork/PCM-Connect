# Connectathon Documentation Review - Key Findings

## Documents Reviewed

From https://github.com/8400TheHealthNetwork/PCM-Connect/tree/main/Connectathon-docs:

1. **spec-python.md** (717 lines) - Complete technical specification
2. **design-python.md** (786 lines) - Architecture and design patterns
3. **team-quickstart.md** (92 lines) - Deployment and setup guide
4. **אפיון רכיבי פתרון PCM מקור מידע.md** (243 lines) - Hebrew specification

## Concrete Values and Contracts Found

### 1. PCM Endpoints

**Token Endpoint:**
- Path: `/token`
- Method: `POST`
- Content-Type: `application/x-www-form-urlencoded`
- Body parameters:
  - `grant_type=client_credentials` (required)
  - `client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer` (required)
  - `client_assertion=<signed_jwt>` (required)
  - `scope` (optional)

**Token Response:**
```json
{
  "access_token": "<token>",
  "token_type": "Bearer",
  "expires_in": 30
}
```
- Token lifetime: **30 seconds**
- Cache recommendation: refresh proactively (e.g., every 25 seconds) only when active requests exist

**Introspection Endpoint:**
- Path: `/introspect`
- Method: `POST`
- Headers: `Authorization: Bearer <adapter_access_token>`
- Content-Type: `application/x-www-form-urlencoded`
- Body: `token=<opaque_token_from_sp>`

**Introspection Response:**
```json
{
  "active": true,
  "patient": "000000018",
  "scope": "patient/Observation.rs",
  "client_id": "org-hospital-a",
  "consent_id": "consent-12345",
  "baskets": ["basket-1"],
  "access_type": "continuous",
  "sp_organization_id": "org-sp-123",
  "cnf": {
    "x5t#S256": "<thumbprint>"
  },
  "aud": "https://fhir.internal.example.com",
  "iss": "https://pcm-core:3000",
  "iat": 1234567890,
  "exp": 1234567920,
  "jti": "unique-id"
}
```

### 2. Client Assertion JWT Structure

**Header:**
```json
{
  "alg": "ES256",
  "typ": "JWT"
}
```

**Payload:**
```json
{
  "iss": "<adapter_client_id>",
  "sub": "<adapter_client_id>",
  "aud": "<pcm_token_url>",
  "exp": "<now + 60>",
  "iat": "<now>",
  "jti": "<uuid4>"
}
```

**Signing:**
- Algorithm: ES256 (ECDSA P-256 + SHA-256)
- Key: Data source's private key (from PCM-issued certificate or separate assertion key)

### 3. mTLS Configuration

**Certificate Format:**
- PEM format for all certificates
- Bundle download includes: `bundle.json`, `.crt` file, `.key` file

**Required Certificates:**
1. **Client Certificate** (`PCM_MTLS_CERT_PATH`) - for mutual TLS with PCM
2. **Client Private Key** (`PCM_MTLS_KEY_PATH`) - matching the client cert
3. **CA Certificate** (`PCM_CA_CERT_PATH`) - for verifying PCM server certificate

**Certificate Acquisition (Connectathon):**
1. Register data source in PCM Admin UI
2. Enable "Generate PCM client certificate"
3. Download bundle (ZIP or JSON format)
4. Bundle contains all required certificate material

**Trust Modes (Connectathon):**
- Team root CA
- System CA
- Custom CA path
- Pinned certificate thumbprint
- Skip verification (debug only)

### 4. ID Replacement Service

**Endpoint:**
- Path: `/api/v1/resolve`
- Method: `POST`
- Content-Type: `application/json`
- Headers: `Authorization: <from DS_ADAPTER_ID_REPLACEMENT_AUTH>`

**Request:**
```json
{
  "national_id": {
    "system": "http://fhir.health.gov.il/identifier/il-national-id",
    "value": "000000018"
  }
}
```

**Response (Success):**
```json
{
  "patient_id": "12345",
  "resource_reference": "Patient/12345"
}
```

**Error Responses:**
- 404: Patient not found
- Timeout/5xx: Service unavailable

**Retry Configuration:**
- Retries: 3 attempts
- Backoff: 0.5 seconds between attempts

### 5. Internal JWT Structure

**Header:**
```json
{
  "alg": "ES256",
  "typ": "JWT"
}
```

**Payload:**
```json
{
  "iss": "ds-adapter",
  "sub": "<local_patient_id>",
  "aud": "https://fhir-internal:8080",
  "exp": "<now + 300>",
  "iat": "<now>",
  "consent_id": "consent-12345",
  "scope": "patient/Observation.rs",
  "patient": "<local_patient_id>",
  "baskets": ["basket-1"],
  "access_type": "continuous",
  "sp_organization_id": "org-sp-123",
  "correlation_id": "550e8400-..."
}
```

**Key Differences from Client Assertion JWT:**
- `sub` is local patient ID (not client_id)
- Contains consent and authorization context
- Longer expiry (300s vs 60s)
- Used for internal FHIR authentication, not PCM

### 6. FHIR Security Parameter Injection

**Query Parameter:**
```
_security:not=http://fhir.health.gov.il/cs/il-core-main-security-label|V
```

**Injection Rules:**
- Apply to GET requests
- Apply to POST requests ending with `_search`
- Append to existing query string using `URLSearchParams`
- Avoid duplicate injection

### 7. Response Verification

**Forbidden Security Label:**
- System: `http://fhir.health.gov.il/cs/il-core-main-security-label`
- Code: `V`

**Verification Scope:**
- FHIR Bundle: scan all `Bundle.entry[].resource.meta.security[]`
- Single Resource: scan `resource.meta.security[]`
- Contained resources: NOT checked in V1

**On Detection:**
- HTTP 400 (generic OperationOutcome)
- Log CRITICAL audit event
- Do NOT reveal which label was found in client response

### 8. Error Catalog

From Connectathon spec-python.md:

| Error Code | HTTP Status | Issue Code | Display |
|------------|-------------|------------|---------|
| AUTH_001 | 401 | login | Missing or invalid Bearer token |
| AUTH_002 | 401 | login | Token introspection failed |
| AUTH_003 | 401 | login | Token expired |
| AUTH_004 | 403 | forbidden | Consent not valid |
| AUTH_005 | 403 | forbidden | Certificate mismatch |
| ID_001 | 502 | exception | ID service unavailable |
| ID_002 | 404 | not-found | Patient not found |
| FHIR_001 | 502 | exception | FHIR Server unavailable |
| FHIR_002 | 504 | timeout | FHIR Server timeout |
| PCM_001 | 502 | exception | PCM unreachable |
| PCM_002 | 401 | login | PCM token acquisition failed |
| CFG_001 | 500 | exception | Configuration error |
| GEN_001 | 500 | exception | Internal error |

### 9. Audit Event Structure

**Required Fields:**
```json
{
  "timestamp": "2025-01-15T10:30:00.000Z",
  "correlation_id": "550e8400-...",
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

**Patient ID Masking:**
- Format: `****<last_4_digits>`
- Example: `000000018` → `****0018`

**Default Behavior:**
- Response body NOT included in audit (config: `audit.include_response`)
- Audit failures do NOT fail the request
- Targets: stdout JSON (V1), file/Kafka/syslog (future)

### 10. Configuration Defaults

From spec-python.md config.yaml:

```yaml
server:
  port: 8000
  host: "0.0.0.0"
  shutdown_timeout_seconds: 30

pcm:
  base_url: "https://pcm-core:3000"
  token_endpoint: "/token"
  introspect_endpoint: "/introspect"
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

verification:
  enabled: true
  forbidden_labels:
    - "http://fhir.health.gov.il/cs/il-core-main-security-label|V"

audit:
  enabled: true
  format: "json"
  include_response: false
```

## What We Still Need

### From PCM Team

1. **Production PCM endpoint URLs** (base URL, token path, introspection path)
2. **Certificate bundle acquisition process** for production (not Connectathon)
3. **Client ID registration** for this data source
4. **Confirmation**: Is client assertion key the same as mTLS key or separate?
5. **CNF validation policy**: Warning only or strict enforcement?
6. **Introspection field requirements**: Which fields are always present vs optional?

### From Certificate Team

1. **Certificate issuance process** for production environment
2. **Certificate rotation policy** and procedures
3. **CA certificate trust requirements** (custom CA or system CA)
4. **Key generation standards** (key size, algorithm requirements)

### From Internal FHIR Team

1. **Production FHIR server base URL**
2. **JWT claim validation requirements** (which claims are required)
3. **Patient reference format** preference (bare ID vs full reference)
4. **Security label system confirmation** (exact system URL for V-label)

### From ID Replacement Team

1. **Service endpoint URL** (or confirmation that service doesn't exist yet)
2. **Authentication method** (Bearer token, Basic auth, API key, mTLS)
3. **Request/response format** confirmation (matches Connectathon spec?)
4. **Service availability** for V1 vs mock implementation

## Implementation Readiness

**Ready to implement (based on Connectathon docs):**
- ✅ PCM token acquisition flow (client credentials + client assertion)
- ✅ Introspection request/response structure
- ✅ Internal JWT minting structure
- ✅ Response verification logic
- ✅ Audit event structure
- ✅ Error catalog and OperationOutcome format
- ✅ mTLS client setup (pending actual certificates)

**Blocked pending team input:**
- ⏸️ Actual endpoint URLs for dev/staging/prod
- ⏸️ Production certificates
- ⏸️ ID Replacement service integration (can mock for V1)
- ⏸️ FHIR server specific requirements

**Recommendation:**
Proceed with implementation using Connectathon contracts as the API specification. Use mock services and placeholder URLs for local development. Request production configuration from each team in parallel.
