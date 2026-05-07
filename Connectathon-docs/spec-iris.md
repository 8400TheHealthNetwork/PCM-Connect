# DS Adapter — מפרט מלא למפתח (InterSystems IRIS)

> **מטרת המסמך**: מסמך זה מכיל את כל מה שמפתח IRIS + coding agent צריכים כדי לבנות את ה-DS Adapter. הפונקציונליות **זהה לחלוטין** למימוש Python — ההבדלים הם בטכנולוגיה וארכיטקטורה בלבד.
>
> **הערה חשובה**: מסמך זה עשוי לדרוש עדכונים — חלק מהפרטים (JWT ES256 ב-ObjectScript, OTel integration) צריכים אימות מול תיעוד IRIS 2024.1.

---

## 1. מה זה DS Adapter?

**זהה ל-Python** — ראה spec-python.md סעיף 1.

שירות שמקבל בקשה מ-SP, מאמת טוקן מול PCM, ממיר מזהה, יוצר JWT, מזריק פרמטר אבטחה, מעביר ל-FHIR, מאמת תשובה, ומחזיר.

---

## 2. טכנולוגיות

| רכיב | טכנולוגיה |
|-------|-----------|
| פלטפורמה | InterSystems IRIS for Health 2024.1+ |
| ארכיטקטורה | Interoperability Production |
| שפה ראשית | BPL (Business Process Language) — visual designer |
| שפה משנית | ObjectScript (custom activities) |
| FHIR Server | IRIS FHIR Repository (built-in) |
| JWT | ES256 — ObjectScript (%Net.JSON / jose library) |
| mTLS | IRIS SSL/TLS Configuration (configurable) |
| Audit | %SYS.Audit (built-in) |
| Observability | OpenTelemetry + IRIS System Monitor + Prometheus |
| API Docs | OpenAPI/Swagger |
| Deployment | IRIS instance on-premise (namespace) |

---

## 3. Production Architecture

```
Production: DS.Adapter.Production
│
├── Business Service: DS.Adapter.Service.InboundHTTP
│   ├── Adapter: EnsLib.HTTP.InboundAdapter
│   └── Receives HTTP requests, creates AdapterRequest message
│
├── Business Process: DS.Adapter.Process.MainFlow (BPL)
│   ├── Orchestrates the entire flow visually
│   ├── Custom ObjectScript activities for: JWT, cnf, security injection, verification
│   └── Error handling via BPL On Error handlers
│
├── Business Operation: DS.Adapter.Operation.PCMToken
│   ├── Adapter: EnsLib.HTTP.OutboundAdapter
│   ├── SSL Config: DS.Adapter.PCM.SSL (if mtls_client=true)
│   └── POST /token
│
├── Business Operation: DS.Adapter.Operation.PCMIntrospect
│   ├── Adapter: EnsLib.HTTP.OutboundAdapter
│   ├── SSL Config: DS.Adapter.PCM.SSL (if mtls_client=true)
│   └── POST /introspect
│
├── Business Operation: DS.Adapter.Operation.IDReplacement
│   ├── Adapter: EnsLib.HTTP.OutboundAdapter
│   ├── Retry Count: 3 (configurable)
│   ├── Retry Interval: 0.5s (configurable)
│   └── POST /api/v1/resolve
│
├── Business Operation: DS.Adapter.Operation.FHIRForward
│   ├── Adapter: EnsLib.HTTP.OutboundAdapter
│   ├── Response Timeout: 30s (configurable)
│   └── Forward request to IRIS FHIR Repository
│
└── Business Operation: DS.Adapter.Operation.Audit
    └── Writes to %SYS.Audit
```

---

## 4. Request Flow — מפורט

### 4.1 Happy Path

```
1. Gateway → InboundHTTP Business Service:
   GET /fhir/Observation?patient=000000018
   Headers: Authorization: Bearer <opaque_token>, X-Correlation-ID: <uuid>

2. Business Service creates DS.Adapter.Message.AdapterRequest:
   - Extracts: Method, Path, QueryString, BearerToken, CorrelationId, SourceIP, Headers, Body
   - If X-Correlation-ID missing → generate $System.Util.CreateGUID()
   - Sends message to MainFlow Business Process

3. BPL Step: GetPCMToken
   - Check ^DS.Adapter.TokenCache global:
     If token exists AND $ZTimestamp < expires_at → use cached
     Else → Call PCMToken Operation:
       - Build client_assertion JWT (ObjectScript custom activity)
       - Send TokenRequest message
       - Receive TokenResponse
       - Store in ^DS.Adapter.TokenCache

4. BPL Step: Introspect
   - Call PCMIntrospect Operation:
     - Send IntrospectRequest (adapter_token + sp_opaque_token)
     - Receive IntrospectResponse
   - If Active = 0 → Error branch → return 401 (AUTH_002)

5. BPL Step: ValidateCnf (ObjectScript custom activity)
   - If CnfThumbprint exists:
     - Compare with client cert SHA-256
     - If mismatch → $$$LOGWARNING (do NOT block)

6. BPL Step: ResolveID
   - Call IDReplacement Operation:
     - Send IDResolveRequest (national_id system + value)
     - Receive IDResolveResponse
   - If Error = "patient_not_found" → return 404 (ID_002)
   - If Error = "service_unavailable" → return 502 (ID_001)

7. BPL Step: MintJWT (ObjectScript custom activity)
   - Build JWT payload (same claims as Python — see section 5)
   - Sign with ES256 using private key from IRIS Credentials
   - Output: signed JWT string

8. BPL Step: InjectSecurity (ObjectScript custom activity)
   - If Method = "GET" OR (Method = "POST" AND Path contains "_search"):
     - Append to QueryString: &_security:not=http://fhir.health.gov.il/cs/il-core-main-security-label|V

9. BPL Step: ForwardFHIR
   - Call FHIRForward Operation:
     - Send FHIRForwardRequest (URL, Method, InternalJWT, Body, CorrelationId)
     - Receive FHIRForwardResponse
   - On timeout → return 504 (FHIR_002)
   - On error → return 502 (FHIR_001)

10. BPL Step: VerifyResponse (ObjectScript custom activity)
    - If verification enabled:
      - Parse response JSON
      - Scan for forbidden security labels
      - If found → CRITICAL audit + return 400
    - If disabled → skip

11. BPL Step: WriteAudit
    - Call Audit Operation with all fields
    - Async (do not wait for completion)

12. BPL Step: Reply
    - Build AdapterResponse (StatusCode, Body, Headers, CorrelationId)
    - Send back to Business Service
    - Business Service returns HTTP response to caller
```

---

## 5. JWT Internal Claims (זהה ל-Python)

```json
{
  "iss": "ds-adapter",
  "sub": "<local_patient_id>",
  "aud": "<fhir_server_base_url>",
  "exp": "<now + expiry_seconds>",
  "iat": "<now>",
  "consent_id": "<from introspection>",
  "scope": "<from introspection>",
  "patient": "<local_patient_id>",
  "baskets": [
    {
      "code": "laboratoryTests",
      "system": "http://fhir.health.gov.il/cs/hdp-information-buckets",
      "historical_depth": "2024-01-01"
    }
  ],
  "access_type": "continuous",
  "sp_organization_id": "<from introspection>",
  "correlation_id": "<correlation_id>"
}
```

Signed with ES256 (ECDSA P-256).

---

## 6. Message Classes

### 6.1 AdapterRequest

```objectscript
Class DS.Adapter.Message.AdapterRequest Extends Ens.Request
{
  Property Method As %String;           // GET, POST, PUT, DELETE, PATCH
  Property Path As %String(MAXLEN=2048);
  Property QueryString As %String(MAXLEN=4096);
  Property BearerToken As %String(MAXLEN=4096);
  Property CorrelationId As %String;
  Property SourceIP As %String;
  Property ContentType As %String;
  Property Body As %Stream.GlobalCharacter;
}
```

### 6.2 AdapterResponse

```objectscript
Class DS.Adapter.Message.AdapterResponse Extends Ens.Response
{
  Property StatusCode As %Integer;
  Property ContentType As %String;
  Property Body As %Stream.GlobalCharacter;
  Property CorrelationId As %String;
}
```

### 6.3 TokenRequest / TokenResponse

```objectscript
Class DS.Adapter.Message.TokenRequest Extends Ens.Request
{
  Property ClientAssertionJWT As %String(MAXLEN=4096);
}

Class DS.Adapter.Message.TokenResponse Extends Ens.Response
{
  Property AccessToken As %String(MAXLEN=2048);
  Property ExpiresIn As %Integer;
  Property Error As %String;
}
```

### 6.4 IntrospectRequest / IntrospectResponse

```objectscript
Class DS.Adapter.Message.IntrospectRequest Extends Ens.Request
{
  Property AdapterToken As %String(MAXLEN=2048);
  Property SPToken As %String(MAXLEN=4096);
}

Class DS.Adapter.Message.IntrospectResponse Extends Ens.Response
{
  Property Active As %Boolean;
  Property Patient As %String;
  Property Scope As %String(MAXLEN=4096);
  Property ConsentId As %String;
  Property BasketsJSON As %String(MAXLEN=32000);  // JSON array
  Property AccessType As %String;
  Property SPOrganizationId As %String;
  Property CnfThumbprint As %String;
  Property Exp As %Integer;
  Property Error As %String;
}
```

### 6.5 IDResolveRequest / IDResolveResponse

```objectscript
Class DS.Adapter.Message.IDResolveRequest Extends Ens.Request
{
  Property NationalIdSystem As %String;
  Property NationalIdValue As %String;
}

Class DS.Adapter.Message.IDResolveResponse Extends Ens.Response
{
  Property PatientId As %String;
  Property ResourceReference As %String;
  Property Error As %String;  // "" | "patient_not_found" | "service_unavailable"
}
```

### 6.6 FHIRForwardRequest / FHIRForwardResponse

```objectscript
Class DS.Adapter.Message.FHIRForwardRequest Extends Ens.Request
{
  Property URL As %String(MAXLEN=4096);
  Property Method As %String;
  Property InternalJWT As %String(MAXLEN=4096);
  Property CorrelationId As %String;
  Property ContentType As %String;
  Property Body As %Stream.GlobalCharacter;
}

Class DS.Adapter.Message.FHIRForwardResponse Extends Ens.Response
{
  Property StatusCode As %Integer;
  Property ContentType As %String;
  Property Body As %Stream.GlobalCharacter;
  Property Error As %String;
}
```

### 6.7 AuditRequest

```objectscript
Class DS.Adapter.Message.AuditRequest Extends Ens.Request
{
  Property Timestamp As %String;
  Property CorrelationId As %String;
  Property SourceIP As %String;
  Property Method As %String;
  Property Path As %String;
  Property FHIRScope As %String;
  Property PatientId As %String;  // masked: ****0018
  Property SPOrganizationId As %String;
  Property ConsentId As %String;
  Property ResponseStatus As %Integer;
  Property ResponseTimeMs As %Float;
  Property Error As %String;
  Property Severity As %String;  // "info" | "critical"
}
```

---

## 7. Configuration

### 7.1 Production Settings (per Business Operation)

| Operation | Setting | Default |
|-----------|---------|---------|
| PCMToken | HTTP Server | pcm-core |
| PCMToken | HTTP Port | 3000 |
| PCMToken | SSL Configuration | DS.Adapter.PCM.SSL |
| PCMIntrospect | HTTP Server | pcm-core |
| PCMIntrospect | HTTP Port | 3000 |
| PCMIntrospect | SSL Configuration | DS.Adapter.PCM.SSL |
| IDReplacement | HTTP Server | id-service |
| IDReplacement | HTTP Port | 9000 |
| IDReplacement | Response Timeout | 1 |
| IDReplacement | Retry Count | 3 |
| IDReplacement | Retry Interval | 0.5 |
| FHIRForward | HTTP Server | localhost |
| FHIRForward | HTTP Port | 52773 |
| FHIRForward | Response Timeout | 30 |

### 7.2 Custom Configuration Global

```objectscript
// ^DS.Adapter.Config("jwt","issuer") = "ds-adapter"
// ^DS.Adapter.Config("jwt","expiry_seconds") = 300
// ^DS.Adapter.Config("jwt","algorithm") = "ES256"
// ^DS.Adapter.Config("verification","enabled") = 1
// ^DS.Adapter.Config("verification","forbidden_labels",1) = "http://fhir.health.gov.il/cs/il-core-main-security-label|V"
// ^DS.Adapter.Config("mtls_client") = 1
// ^DS.Adapter.Config("audit","patient_mask_length") = 4
```

### 7.3 SSL/TLS Configuration (Management Portal)

| Name | Type | Cert | Key | CA | Protocols |
|------|------|------|-----|-----|-----------|
| DS.Adapter.PCM.SSL | Client | client.crt | client.key | ca.crt | TLSv1.2+ |

### 7.4 mTLS Modes (same as Python)

- `^DS.Adapter.Config("mtls_client") = 1` → Operations use SSL Configuration
- `^DS.Adapter.Config("mtls_client") = 0` → Operations use no SSL (external proxy)

---

## 8. Error Handling

**זהה לחלוטין ל-Python** — אותם error codes, אותם HTTP statuses, אותו OperationOutcome format.

ראה spec-python.md סעיף 7 לקטלוג המלא.

ב-IRIS, errors מנוהלים דרך:
- BPL `<if>` conditions (active=false, patient not found)
- BPL `<catch>` blocks (timeouts, connection errors)
- Business Operation `FailureTimeout` settings

---

## 9. Audit (%SYS.Audit)

```objectscript
ClassMethod WriteAudit(req As DS.Adapter.Message.AuditRequest) As %Status
{
  Set auditJSON = {}
  Set auditJSON."correlation_id" = req.CorrelationId
  Set auditJSON."source_ip" = req.SourceIP
  Set auditJSON."method" = req.Method
  Set auditJSON."path" = req.Path
  Set auditJSON."fhir_scope" = req.FHIRScope
  Set auditJSON."patient_id" = req.PatientId
  Set auditJSON."sp_organization_id" = req.SPOrganizationId
  Set auditJSON."consent_id" = req.ConsentId
  Set auditJSON."response_status" = req.ResponseStatus
  Set auditJSON."response_time_ms" = req.ResponseTimeMs
  If (req.Error '= "") { Set auditJSON."error" = req.Error }
  
  // Write to IRIS Audit Database
  Set sc = ##class(%SYS.Audit).Audit(
    "DSAdapter",           // Source
    "DataAccess",          // Type  
    req.Severity,          // Event (info/critical)
    auditJSON.%ToJSON()    // Description
  )
  Quit sc
}
```

---

## 10. ID Replacement — Open Topic

הארגון בוחר את הגישה. ה-Business Operation מממש את ה-contract:

**Option A**: External REST service (same contract as Python)
**Option B**: Direct IRIS FHIR query: `Patient?identifier=system|value`
**Option C**: IRIS MPI (HealthShare)
**Option D**: Configurable — Production setting selects strategy

---

## 11. Health/Ready/Metrics

REST dispatch class נפרד מה-Production:

```objectscript
Class DS.Adapter.REST.HealthAPI Extends %CSP.REST
{
  XData UrlMap [ XMLNamespace = "http://www.intersystems.com/urlmap" ]
  {
    <Routes>
      <Route Url="/health" Method="GET" Call="Health"/>
      <Route Url="/ready" Method="GET" Call="Ready"/>
      <Route Url="/metrics" Method="GET" Call="Metrics"/>
    </Routes>
  }
  
  ClassMethod Health() As %Status
  {
    Set %response.ContentType = "application/json"
    Write {"status": "ok"}
    Quit $$$OK
  }
  
  ClassMethod Ready() As %Status
  {
    // Check FHIR server connectivity
    // Check PCM connectivity
    // Return 200 if both OK, 503 if any fails
  }
  
  ClassMethod Metrics() As %Status
  {
    // Return Prometheus text format metrics
  }
}
```

Web Application: `/ds-adapter-health/`

---

## 12. Observability

### 12.1 OpenTelemetry
- Same spans as Python (see spec-python.md section 9)
- IRIS 2024.1 supports OTel SDK
- Configure OTLP exporter

### 12.2 IRIS System Monitor + Prometheus
- Install isc-prometheus exporter
- Exposes IRIS system metrics (cache, processes, locks)
- Custom application metrics via `%SYS.Monitor.AbstractSensor`

### 12.3 Built-in Production Monitoring
- Message Trace: every message between components is stored
- Event Log: errors and warnings
- Queue monitoring: detect backlogs
- Visual Trace: see full request flow in Management Portal

---

## 13. Deployment

### 13.1 Namespace Setup

```
Namespace: DSADAPTER
Databases: DSADAPTER-DATA (data), DSADAPTER-CODE (code)
Web Applications:
  - /ds-adapter/ → InboundHTTP Business Service
  - /ds-adapter-health/ → HealthAPI REST class
```

### 13.2 Installation Steps

1. Create namespace `DSADAPTER` with databases
2. Import all classes (Message, Service, Process, Operations, Utils)
3. Create SSL/TLS Configuration `DS.Adapter.PCM.SSL` (if mtls_client)
4. Set up Credentials (JWT signing key, ID Replacement auth)
5. Initialize `^DS.Adapter.Config` global with defaults
6. Create and configure Production `DS.Adapter.Production`
7. Start Production
8. Create Web Applications for inbound HTTP and health endpoints
9. Test with GET /ds-adapter-health/health

---

## 14. Testing

### 14.1 Unit Tests (%UnitTest)

| Class | Tests |
|-------|-------|
| DS.Adapter.Test.JWTMint | Correct claims, correct signature, correct expiry |
| DS.Adapter.Test.Verification | Bundle pass, Bundle fail (V label), single resource fail, disabled skip |
| DS.Adapter.Test.SecurityInjection | GET → inject, POST _search → inject, POST create → no inject |
| DS.Adapter.Test.TokenCache | Cache hit, cache miss, cache expired |
| DS.Adapter.Test.ErrorBuilder | Each error code → correct OperationOutcome |

### 14.2 Integration Tests (Production Testing)

| Scenario | Setup | Expected |
|----------|-------|----------|
| Happy path | Mock PCM + Mock FHIR | 200 + Bundle |
| Inactive token | Mock PCM returns active=false | 401 |
| Patient not found | Mock ID returns 404 | 404 |
| FHIR timeout | Mock FHIR delays > 30s | 504 |
| Forbidden label | Mock FHIR returns Bundle with V | 400 |

---

## 15. Differences from Python Implementation

| Aspect | Python | IRIS |
|--------|--------|------|
| Entry point | FastAPI route handler | Business Service (HTTP Inbound) |
| Flow orchestration | async function calls | BPL visual process |
| HTTP calls | httpx.AsyncClient | EnsLib.HTTP.OutboundAdapter |
| Retry | Custom loop with backoff | Built-in Operation retry settings |
| Token cache | Module-level variable + asyncio.Lock | ^DS.Adapter.TokenCache global |
| JWT signing | PyJWT library | ObjectScript custom code |
| Config | YAML + env vars (pydantic) | Production settings + ^Config global |
| Audit | Kafka + File + Syslog | %SYS.Audit |
| Logging | structlog → stdout/stderr | $$$LOGINFO, $$$LOGWARNING, $$$LOGERROR |
| Deployment | Docker container | IRIS namespace on-premise |
| Monitoring | OTel only | OTel + Production Message Trace + System Monitor |
| Error queues | N/A (stateless) | Built-in (failed messages stored) |

---

## 16. Security Notes

**זהה ל-Python** — ראה spec-python.md סעיף 17.

בנוסף ב-IRIS:
- Private keys stored in IRIS Credentials (not in globals)
- SSL/TLS Configuration managed via Management Portal
- %SYS.Audit is tamper-proof (system-level)
- Production runs under a dedicated IRIS user with minimal privileges
