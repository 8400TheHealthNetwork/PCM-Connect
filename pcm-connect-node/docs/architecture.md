# PCM/FHIR Data Source Adapter - Architecture

## 1. System Purpose

The Data Source Adapter is a Node.js/TypeScript service that acts as a Policy Enforcement Point (PEP) between external Service Providers and the organization's internal FHIR server.

The adapter receives FHIR R4 REST requests with an opaque Bearer token, validates authorization through PCM, resolves the patient identifier to a local FHIR patient ID, mints a short-lived internal JWT, forwards the request to the internal FHIR server, verifies the response, and returns either the FHIR response or a safe FHIR OperationOutcome.

The adapter is implemented as a FHIR R4 REST proxy. It does not require a dedicated FHIR SDK/package in V1.

## 2. High-Level Request Flow

1. External Service Provider sends a FHIR R4 REST GET/search request with an opaque Bearer token.
2. Adapter extracts or creates `X-Correlation-ID`.
3. Adapter acquires a PCM client access token using client credentials and signed client assertion.
4. Adapter introspects the opaque Service Provider token with PCM.
5. Adapter validates that the token is active and extracts patient identifier, scopes, `client_id`, consent/intent metadata, and expiry.
6. Adapter calls ID Replacement to map the business patient identifier to a local FHIR patient identifier.
7. Adapter mints a short-lived internal ES256 JWT for the internal FHIR server.
8. Adapter builds the internal FHIR request using safe URL handling.
9. Adapter injects the local patient identifier and forbidden V-label exclusion into the query where relevant.
10. Adapter forwards the request to the internal FHIR server with the internal JWT.
11. Adapter verifies the returned FHIR Bundle or Resource for forbidden `meta.security` labels.
12. Adapter returns the original FHIR response if clean, or a safe OperationOutcome if blocked.
13. Adapter writes an audit event for every request.

## 3. Component Architecture

- `ConfigModule` - typed configuration, environment overrides, secrets from environment variables.
- `PcmModule` - PCM client token acquisition and token introspection.
- `IdentityModule` - ID Replacement client interface.
- `InternalJwtModule` - internal ES256 JWT minting.
- `FhirModule` - FHIR R4 REST proxy forwarding.
- `VerificationModule` - response verification for forbidden security labels.
- `AuditModule` - dedicated audit service, separate from normal application logs.
- `CommonModule` - shared errors, OperationOutcome builder, correlation ID utilities.
- `HealthModule` - health and readiness endpoints.
- `ObservabilityModule` - metrics, structured logs, tracing hooks.

## 4. Main Sequence

```text
Service Provider
  -> Adapter: FHIR GET/search + opaque Bearer token
  -> PCM: acquire client token
  -> PCM: introspect opaque token
  -> ID Replacement: resolve patient identifier
  -> Adapter: mint internal JWT
  -> Internal FHIR: forward request with internal JWT
  -> Adapter: verify FHIR response
  -> Service Provider: FHIR response or OperationOutcome
  -> AuditService: write audit event
```

## 5. Security Model

- The external opaque token is never trusted directly.
- PCM introspection is the authorization source.
- Introspection is not cached in V1.
- PCM client access token may use optional lazy in-memory cache only.
- The internal JWT is short-lived and signed with ES256.
- The internal JWT carries patient and scope context required by the internal FHIR server.
- The adapter injects a V-label exclusion into FHIR queries as the first line of defense.
- Response verification scans returned FHIR data as a second line of defense.
- Security failures must not reveal sensitive details to the Service Provider.

## 6. FHIR R4 REST Proxy Behavior

V1 supports GET/search FHIR R4 REST requests only.

The adapter should:

- Preserve original query parameters.
- Use `URL` and `URLSearchParams`.
- Avoid manual string concatenation.
- Inject the local patient identifier where required.
- Inject `_security:not=http://fhir.health.gov.il/cs/il-core-main-security-label|V`.
- Avoid duplicate `_security:not` parameters unless explicitly configured.
- Forward the request to the internal FHIR server with `Authorization: Bearer <internal_jwt>`.

V1 does not assume or require a dedicated FHIR SDK/package.

## 7. Response Verification

The verifier must inspect:

- FHIR Bundles: `Bundle.entry[].resource.meta.security`
- Single FHIR Resources: `resource.meta.security`

If a forbidden label is found, especially:

```text
system = http://fhir.health.gov.il/cs/il-core-main-security-label
code = V
```

Then:

- The response must be blocked.
- A critical audit event must be written.
- The Service Provider receives a generic FHIR OperationOutcome.
- The response must not reveal that V-labeled data exists.

## 8. Error Handling

All errors are returned as FHIR OperationOutcome.

Rules:

- Do not expose stack traces, internal URLs, certificate details, or sensitive authorization details.
- Use safe/generic diagnostics for security-sensitive failures.
- Put detailed technical information only in internal logs and audit.
- Always include or propagate `X-Correlation-ID`.

## 9. Audit and Observability

Audit is separate from application logging.

V1 audit:

- Every request must produce an audit event.
- Audit events are structured JSON.
- Audit may be written to stdout in V1 through a dedicated `AuditService`.
- The design must remain open for future file, Kafka, or SIEM targets.
- Response bodies are not logged by default.

Observability:

- Health endpoint.
- Readiness endpoint.
- Metrics endpoint or metrics-ready structure.
- Structured application logs with correlation ID.

## 10. V1 Boundaries

See `docs/v1-scope.md`.

V1 intentionally focuses on a minimal secure read/search proxy flow.

Deferred:

- POST/PUT/PATCH/DELETE FHIR operations.
- Introspection cache.
- Redis/distributed cache.
- Proactive PCM token refresh.
- Full ID Replacement implementation.
- Kafka/SIEM audit integration.
- Certificate auto-rotation.
- UI/admin dashboard.

## 11. Open Questions

See `docs/open-questions.md`.

Open questions must be resolved before production hardening, but they should not block the V1 skeleton and mocked end-to-end flow.

## 12. External References

This implementation is aligned with the PCM Connectathon specifications and architecture:

**PCM-Connect Connectathon Documentation**
- Repository: https://github.com/8400TheHealthNetwork/PCM-Connect/tree/main/Connectathon-docs
- Key documents:
  - `spec-python.md` - Complete technical specification for data source adapters (Python/FastAPI reference)
  - `design-python.md` - Detailed architecture and flow diagrams
  - `team-quickstart.md` - Connectathon deployment and setup guide
  - `אפיון רכיבי פתרון PCM מקור מידע.md` - Hebrew specification for PCM data source integration

**Implementation Notes:**
- This Node.js/TypeScript implementation follows the same architectural patterns and API contracts as the Python reference
- PCM endpoint paths, introspection response format, and security requirements are based on the Connectathon specifications
- Configuration structure (YAML + environment variables) mirrors the reference implementation
- The Connectathon docs serve as the authoritative source for PCM integration contracts

**Differences from Reference:**
- Technology stack: Node.js + NestJS + Fastify instead of Python + FastAPI
- JWT library: `jose` instead of PyJWT
- HTTP client: Node.js native `https` / `axios` / `undici` instead of httpx
- Configuration: NestJS ConfigModule instead of pydantic-settings