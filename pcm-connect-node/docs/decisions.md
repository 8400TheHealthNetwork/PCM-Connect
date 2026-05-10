# Architecture Decisions

## 1. Technology Stack

### ADR-001: Node.js + TypeScript + NestJS with Fastify
- **Status**: Accepted
- **Context**: PCM/FHIR spec was written for Python/FastAPI. We need equivalent Node.js implementation with better async I/O performance for high-throughput proxy operations.
- **Decision**: 
  - Runtime: Node.js 20+ with TypeScript
  - Framework: NestJS with `@nestjs/platform-fastify` adapter
  - HTTP Engine: `fastify` (not Express)
  - JWT Library: `jose` for ES256 signing (modern, TypeScript-native)
- **Rationale**:
  - NestJS provides modular architecture, dependency injection, and built-in validation similar to FastAPI
  - Fastify offers better performance than Express for proxy scenarios (async/await optimization)
  - `jose` is the recommended modern JWT library with full ES256 support
- **Consequences**: 
  - Strong typing and compile-time safety
  - Requires team familiarity with NestJS decorators and DI patterns
  - Performance suitable for 100s-1000s req/sec

## 2. Caching Decisions

### ADR-002: No Introspection Token Cache in V1
- **Status**: Accepted
- **Context**: PCM spec recommends caching introspected tokens to reduce load. However, caching adds complexity around invalidation, staleness, and potential security risks if consent is revoked.
- **Decision**: **Do not cache introspection results in V1**. Every incoming request triggers fresh PCM introspection.
- **Rationale**:
  - Simpler implementation for initial version
  - Eliminates risk of serving stale/revoked consent
  - PCM introspection latency expected to be acceptable (<100ms)
- **Consequences**: 
  - Higher load on PCM introspection endpoint
  - Slightly higher latency per request
  - Easier to reason about security guarantees
- **Future**: Consider caching in V2 if PCM latency becomes bottleneck

### ADR-003: Optional Lazy PCM Client Token Cache
- **Status**: Accepted
- **Context**: PCM client access token (for adapter's own authentication) expires every 30 seconds. Spec suggests proactive refresh "only if active requests exist."
- **Decision**: 
  - Implement **optional in-memory cache** for client access token only
  - **Lazy refresh strategy**: fetch new token when current one expires or doesn't exist
  - **No proactive background refresh** (spec's "only if active" condition is too complex for V1)
  - Config-controlled: `pcm.clientTokenCacheEnabled=true/false` and `pcm.clientTokenCacheSafetyMarginSeconds=5`
- **Rationale**:
  - Reduces PCM token endpoint calls from "every request" to "once per 25-30 seconds"
  - Lazy approach is simpler than tracking "active requests" and running background jobs
  - Safety margin prevents using tokens about to expire
- **Consequences**: 
  - First request after token expiry incurs extra 100-200ms for token fetch
  - Cache disabled by default to keep behavior predictable
  - No Redis or distributed cache in V1

## 3. V1 Scope

### ADR-004: Read-Only FHIR Operations in V1
- **Status**: Accepted
- **Context**: PCM spec examples focus on GET/search operations (e.g., `GET /Observation?category=vital-signs`). Write operations (POST/PUT/DELETE) require different security injection strategies.
- **Decision**: V1 supports **only GET and FHIR search operations**. No POST/PUT/PATCH/DELETE unless explicitly required later.
- **Rationale**:
  - Read operations can inject `_security:not=V` as query param
  - Write operations would need different approach (request body inspection, different error codes)
  - Reduces V1 complexity and security attack surface
- **Consequences**: 
  - Service providers cannot create/update resources through this adapter in V1
  - Clear boundary for V1 testing and security audit
- **Future**: Add write operations in V2 with proper body validation and injection

## 4. Security Decisions

### ADR-005: Internal JWT with ES256
- **Status**: Accepted
- **Context**: Adapter must authenticate to internal FHIR server with secure, short-lived token containing patient context and scopes.
- **Decision**: 
  - Algorithm: **ES256** (ECDSA with P-256 curve and SHA-256)
  - Library: `jose`
  - Private key: from environment variable or file (PEM format)
  - Token lifetime: 60 seconds
  - Claims: `iss`, `sub` (service provider ID), `aud`, `patient` (local resource ID), `scope`, `iat`, `exp`
- **Rationale**:
  - ES256 provides strong security with smaller key sizes than RSA
  - 60-second TTL minimizes risk if token is intercepted
  - `jose` library is well-maintained and TypeScript-native
- **Consequences**: 
  - Requires ES256 key pair generation and secure storage
  - FHIR server must validate ES256 signatures

### ADR-006: Response Verification Enabled by Default
- **Status**: Accepted
- **Context**: Critical security requirement per spec (רכיב 5). Must prevent V-labeled (highly restricted) resources from reaching service providers.
- **Decision**: 
  - **Hard fail** on detection of forbidden `meta.security` labels in response
  - Scan both FHIR Bundles (`Bundle.entry[].resource.meta.security`) and single resources (`resource.meta.security`)
  - Default forbidden label: `system=http://fhir.health.gov.il/cs/il-core-main-security-label, code=V`
  - Config toggle: `responseVerification.enabled=true` (default)
  - Additional forbidden labels configurable via YAML array
- **Rationale**:
  - Spec mandates this as "Layer 2" protection (URL injection is Layer 1)
  - Prevents bugs in FHIR server or injection logic from leaking restricted data
- **Consequences**: 
  - Extra parsing and iteration overhead on every response
  - Generic error messages only (no indication that V-labeled data exists)
  - Critical audit log written when V detected

### ADR-007: Safe OperationOutcome for Security Failures
- **Status**: Accepted
- **Context**: When V-labeled data is detected, cannot reveal to service provider that highly restricted data exists for this patient.
- **Decision**: Return generic FHIR OperationOutcome with:
  - HTTP 400 or 403
  - `issue.severity = "error"`
  - `issue.code = "processing"`
  - `issue.diagnostics = "Request could not be processed"` (generic message)
  - No details about V label or resource type
- **Rationale**:
  - Prevents information leakage about existence of sensitive data
  - FHIR-compliant error format
  - Internal audit log captures full details for investigation
- **Consequences**: 
  - Service providers may find error messages unhelpful
  - Debugging requires access to internal audit logs

## 5. Audit and Logging

### ADR-008: Separate Audit from Application Logs
- **Status**: Accepted
- **Context**: Audit events have compliance/legal requirements and must be distinguishable from debug/info logs.
- **Decision**: 
  - **Separate `AuditService`** for audit events only
  - Audit events are structured JSON with fixed schema
  - V1 implementation: write audit JSON to **stdout** (one event per line)
  - Application logs (info, warn, error) go through separate logger (Pino/Winston)
  - Audit events must include: timestamp, service provider ID, patient ID (last 4 digits or hashed), operation, result, correlation ID
- **Rationale**:
  - Infrastructure can route stdout to dedicated audit pipeline (Fluentd, Datadog, SIEM)
  - Keeps audit logic isolated and testable
  - Future-proof for migration to Kafka, files, or external service
- **Consequences**: 
  - Two logging mechanisms in codebase
  - Must ensure audit service never throws exceptions (wrap all I/O)
- **Future**: Add async audit targets (Kafka, HTTP webhook) in V2

### ADR-009: Always Write Audit, Even on Failure
- **Status**: Accepted
- **Context**: Audit trail must be complete for security and compliance.
- **Decision**: Write audit event for **every request**, including:
  - Successful responses
  - Authentication failures (invalid token)
  - Authorization failures (insufficient scopes)
  - Security violations (V-label detected)
  - Internal errors (FHIR server timeout, ID swap failure)
- **Rationale**: 
  - Complete audit trail for investigations
  - Detect patterns of abuse or system issues
- **Consequences**: 
  - Higher log volume
  - Audit service must be robust and never block request path

## 6. ID Replacement

### ADR-010: Separate Local ID and Resource Reference
- **Status**: Accepted
- **Context**: FHIR servers may expect patient references in different formats. Spec doesn't clarify exact format.
- **Decision**: ID Replacement service returns TWO fields:
  ```typescript
  {
    localPatientId: "abc123",          // Bare ID
    resourceReference: "Patient/abc123" // Full reference
  }
  ```
  Adapter uses the appropriate field based on FHIR server expectations (TBD).
- **Rationale**:
  - Different FHIR servers handle `patient` param differently:
    - Some expect `patient=abc123` (bare ID)
    - Some expect `patient=Patient/abc123` (full reference)
  - Separating fields allows adapter to choose correct format
- **Consequences**: 
  - ID Replacement service must return both formats
  - Configuration needed to specify which format internal FHIR expects
- **Open Question**: Need to verify with internal FHIR server team which format they expect

## 7. URL Handling

### ADR-011: Use URL/URLSearchParams for Query Construction
- **Status**: Accepted
- **Context**: Manual string concatenation of query params is error-prone (encoding, duplicates, special chars like `|`).
- **Decision**: 
  - Use native `URL` and `URLSearchParams` APIs for all query manipulation
  - Parse incoming request URL to `URL` object
  - Add/modify params via `URLSearchParams` methods
  - Ensure `|` character in `_security:not=system|code` is properly encoded
  - Preserve all existing query params from original request
  - Check for existing `_security:not` param before adding (avoid duplicates unless config allows multiple)
- **Rationale**:
  - Handles encoding automatically
  - Prevents injection vulnerabilities
  - Easier to test and maintain
- **Example**:
  ```typescript
  const url = new URL(originalUrl, fhirBaseUrl);
  url.searchParams.set('patient', localPatientId);
  url.searchParams.append('_security:not', 'http://fhir.health.gov.il/cs/il-core-main-security-label|V');
  ```
- **Consequences**: 
  - Slight performance overhead (negligible for proxy)
  - More verbose than string concatenation but much safer
