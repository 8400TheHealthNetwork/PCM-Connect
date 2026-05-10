# V1 Implementation Scope

## 1. V1 Goal

Build a **minimal but secure** PCM/FHIR Data Source Adapter that:
- Enforces PCM consent authorization for external service providers
- Prevents leakage of V-labeled (highly restricted) patient data
- Provides a clean, modular foundation for future enhancements

**Focus**: Read/search flow from external Service Provider → PCM authorization → internal FHIR server.

**Non-goal**: Feature completeness. V1 is intentionally limited to validate the architecture and security model.

## 2. In Scope for V1

### Project Setup
-  Node.js 20+ with TypeScript (strict mode)
-  NestJS framework with `@nestjs/platform-fastify` adapter
-  `fastify` HTTP engine for performance
-  `jose` library for ES256 JWT operations
-  YAML configuration + environment variable overrides
-  Secrets loaded from environment only (never YAML)

### FHIR Proxy Endpoint
-  Single proxy endpoint: `GET /fhir/*` (catch-all route)
-  Extract Bearer opaque token from `Authorization` header
-  Forward GET/search requests only (no POST/PUT/PATCH/DELETE)
-  Preserve original FHIR query parameters

### PCM Integration
-  **PCM Client Token Service**: Acquire access token for adapter's own authentication
  - mTLS connection with client cert/key
  - Generate and sign `client_assertion` JWT
  - POST to PCM token endpoint
  - Parse `access_token`, `expires_in` from response
-  **Optional lazy in-memory cache** for client token:
  - Config flags: `pcm.clientTokenCacheEnabled`, `pcm.clientTokenCacheSafetyMarginSeconds`
  - Lazy fetch (no proactive refresh)
  - Default: cache disabled
-  **PCM Introspection Service**: Validate opaque token from service provider
  - POST to PCM introspection endpoint with adapter's client token
  - Parse response: `active`, `patient`, `scope`, `client_id`, `exp`
  - **No caching** of introspection results in V1
  - Return error if `active=false`

### Identity Services
-  **ID Replacement Client**: Call external service to map business patient ID → FHIR resource ID
  - Interface definition (REST client)
  - Request: `{ patient_identifier, system }`
  - Response: `{ localPatientId, resourceReference }`
  - Mock implementation for testing
-  **Internal JWT Service**: Mint ES256-signed JWT for FHIR server authentication
  - Algorithm: ES256 (ECDSA P-256 + SHA-256)
  - Claims: `iss`, `sub`, `aud`, `patient`, `scope`, `iat`, `exp`
  - TTL: 60 seconds
  - Private key from PEM file or env var

### FHIR Forwarding
-  **FHIR Proxy Service**: Forward modified request to internal FHIR server
  - Use `URL` and `URLSearchParams` for safe query manipulation (no string concatenation)
  - Inject query parameters:
    - `patient=[localPatientId or resourceReference]` (config-driven format)
    - `_security:not=http://fhir.health.gov.il/cs/il-core-main-security-label|V`
  - Preserve existing query params
  - Send internal JWT as `Authorization: Bearer <jwt>`
  - HTTP client with configurable timeout

### Response Verification
-  **Response Verification Service**: Scan for forbidden security labels
  - Parse FHIR response (Bundle or single Resource)
  - Iterate `Bundle.entry[].resource.meta.security[]` for Bundles
  - Check `resource.meta.security[]` for single resources
  - Detect forbidden labels: `system=...il-core-main-security-label, code=V`
  - **Hard fail** if V detected:
    - Return generic FHIR OperationOutcome (HTTP 400/403)
    - Write critical audit event
    - Do NOT reveal V-label existence to service provider
  - Pass through clean responses unchanged
  - Config toggle: `responseVerification.enabled` (default: true)

### Error Handling
-  **OperationOutcome Builder**: Generate FHIR-compliant error responses
  - Generic messages for security failures: "Request could not be processed"
  - More detailed messages for client errors (invalid token, missing params)
  - Always include `issue.severity`, `issue.code`, `issue.diagnostics`
  - Propagate or generate `X-Correlation-ID` header

### Audit and Observability
-  **Audit Service**: Write structured audit events (separate from app logs)
  - Output: JSON to stdout (one event per line)
  - Schema: timestamp, correlationId, serviceProviderId, patientId (hashed/last 4 digits), operation, result, details
  - Write audit for **every request** (success, failure, security violation)
  - Never throw exceptions (wrap all I/O)
-  **Health/Readiness Endpoints**: `/health` and `/ready` for k8s/monitoring
  - Health: returns 200 if app is running
  - Readiness: checks dependencies (PCM reachable, FHIR reachable)
-  **Metrics Endpoint**: `/metrics` in Prometheus format
  - Request counters by status code
  - Request duration histograms
  - PCM token acquisition latency
  - V-label detection counter

### Testing
-  **Unit Tests**: For all services (PCM, JWT, verification, audit, etc.)
  - Mock external dependencies
  - Test edge cases and error paths
-  **Integration Tests**: End-to-end flow with mocks
  - Mock PCM token endpoint
  - Mock PCM introspection endpoint
  - Mock ID replacement service
  - Mock internal FHIR server
  - Verify full request/response cycle
  - Verify V-label blocking
  - Verify audit events written

## 3. Out of Scope for V1

### HTTP Methods
- POST, PUT, PATCH, DELETE FHIR operations (different security model needed)
- Bulk operations, batch requests

### Caching
- Introspection token caching (simplifies V1, reduces staleness risk)
- Redis or distributed cache
- Proactive background PCM token refresh (complex "active requests" detection)

### ID Replacement
- Full ID Replacement service implementation (V1 only defines client interface)
- Multiple ID mapping strategies per organization
- Cryptographic pseudonymization within adapter

### Audit Advanced Features
- Kafka or message queue audit targets
- HTTP webhook to external SIEM
- File-based audit logs
- Audit event buffering/batching

### Certificate Management
- Automatic mTLS certificate rotation
- CRL (Certificate Revocation List) checking
- Certificate expiry warnings

### FHIR Advanced Features
- Authorization logic beyond forwarding PCM scopes
- Custom FHIR search parameter parsing
- GraphQL or other query languages
- FHIR Subscription support
- Resource-level permission checks (rely on FHIR server)

### Operational Features
- Kubernetes deployment manifests, Helm charts
- Distributed tracing (OpenTelemetry)
- Circuit breaker patterns
- Rate limiting per service provider
- Advanced monitoring dashboards (Grafana)
- Horizontal scaling coordination (V1 is stateless, scales naturally)

### UI/Admin
- Admin dashboard for configuration
- Manual token introspection UI
- Audit log viewer

## 4. V1 Success Criteria

V1 will be considered successful when:

### Functional
1. ✅ A full end-to-end mocked request flows through all components:
   - External service provider calls `/fhir/Observation?category=vital-signs` with opaque Bearer token
   - Adapter acquires PCM client token (or uses cached one)
   - Adapter introspects opaque token with PCM
   - Adapter resolves patient ID via ID Replacement client
   - Adapter mints internal JWT
   - Adapter forwards to FHIR with injected params
   - Adapter verifies response for V-labels
   - Adapter returns clean response or OperationOutcome error
   - Audit event written for request

2. ✅ Security verification works correctly:
   - V-labeled resources are detected in Bundle responses
   - V-labeled single resources are detected
   - Adapter returns generic error (no info leakage)
   - Critical audit event written

3. ✅ Error handling produces safe responses:
   - Invalid tokens return FHIR OperationOutcome
   - PCM introspection failures return generic errors
   - ID Replacement failures handled gracefully
   - FHIR server timeouts/errors handled

### Quality
4. ✅ Code is modular and testable:
   - Each service has single responsibility
   - Dependencies injected via NestJS DI
   - Easy to swap mocks for tests

5. ✅ Unit test coverage >80% for core services

6. ✅ Integration tests cover happy path and key error scenarios

### Documentation
7. ✅ README explains how to run locally with mocks

8. ✅ Configuration is documented (`.env.example`)

9. ✅ Architecture decisions are captured (`docs/decisions.md`)

### Performance
10. ✅ Request latency <500ms (with mocks, no network)

11. ✅ No memory leaks in 1000-request test run

### Readiness
12. ✅ Project is ready for real PCM/FHIR integration:
    - Mock interfaces match real API contracts
    - Configuration supports switching to real endpoints
    - No hardcoded URLs or credentials in code
