# Open Questions

Questions to be resolved before or during implementation. Grouped by component/concern.

---

## 1. PCM / Token Handling

### Q1.0: How to Obtain Service Provider Opaque Token for Testing
- **Question**: How can we obtain a valid opaque Service Provider token to test PCM introspection locally?
- **Context**: The adapter's PCM introspection requires an opaque token from a Service Provider. This is different from the adapter's own client token. Connectathon docs show introspection body as `token=<opaque_token_from_sp>` but don't explain how to obtain one.
- **Impact**: Cannot fully test introspection flow without a real Service Provider token
- **Team**: PCM team / Connectathon organizers
- **Status**: Pending - need documentation or test endpoint to obtain Service Provider tokens
- **Options**:
  1. PCM Admin UI provides a "Generate Test Token" feature for registered Service Providers
  2. Connectathon provides sample/mock Service Provider tokens in documentation
  3. We need to register as a Service Provider (in addition to Data Source) to get tokens
  4. Use Postman/curl to simulate Service Provider OAuth flow and obtain token
  5. PCM provides a test token endpoint specifically for adapter development
- **Workaround**: Introspection service and tests implemented, but cannot run `npm run pcm:introspect:check` without a valid opaque token

### Q1.1: PCM Endpoint URLs
- **Question**: What are the exact PCM token and introspection endpoint paths?
- **Context**: Spec mentions token endpoint for `client_credentials` and introspection endpoint, but no exact URLs
- **Impact**: Configuration, integration testing
- **Assumption**: Will use config placeholders like `https://pcm.example.com/oauth/token`

### Q1.2: Client Assertion Audience
- **Question**: What value should be used for the `aud` claim in the `client_assertion` JWT?
- **Context**: OAuth2 JWT assertion requires audience matching the authorization server
- **Impact**: PCM token acquisition may fail with incorrect `aud`
- **Assumption**: Use PCM token endpoint URL as `aud`

### Q1.3: PCM Client Token Cache Default
- **Question**: Should PCM client token cache be enabled by default or disabled?
- **Context**: Cache improves performance but adds complexity
- **Impact**: Default configuration behavior
- **Assumption**: Disabled by default (`pcm.clientTokenCacheEnabled=false`) for predictable behavior

### Q1.4: mTLS Certificate Format
- **Question**: What format are the mTLS certificates (PEM, P12/PKCS12)? Where are they stored?
- **Context**: Node.js `https.Agent` expects PEM by default. Connectathon docs indicate PEM format in bundle downloads.
- **Impact**: Certificate loading, deployment process
- **Assumption**: PEM format, loaded from file paths in config/env
- **Status**: Partially resolved - Connectathon uses PEM, need confirmation for production environment

### Q1.5: PCM Deployment URLs
- **Question**: What are the exact PCM endpoint URLs (base URL, token path, introspection path) for our environment?
- **Context**: Connectathon docs show example: `https://pcm-core:3000` with `/token` and `/introspect`. Production URLs will differ.
- **Impact**: Configuration for dev, staging, and production environments
- **Team**: PCM team must provide deployment-specific URLs
- **Status**: Pending - need URLs from PCM team for each environment

### Q1.6: Certificate Bundle Source
- **Question**: How do we obtain the certificate bundle (client cert, client key, CA cert) for our data source?
- **Context**: Connectathon flow: register data source in PCM Admin → download ZIP/JSON bundle
- **Impact**: Deployment setup, certificate rotation procedures
- **Team**: Certificate team + PCM team for production certificate issuance
- **Status**: Pending - need process for obtaining production certificates

### Q1.7: Client Assertion Key vs mTLS Key
- **Question**: Is the client assertion signing key the same as the mTLS client private key, or separate?
- **Context**: Connectathon docs show both mTLS and client_assertion. Some OAuth2 flows use the same key pair, others separate.
- **Impact**: Configuration complexity, key management
- **Team**: PCM team to clarify key requirements
- **Status**: Pending - configured as separate keys for flexibility

---

## 2. Introspection Response

### Q2.1: PCM Introspection Field Names
- **Question**: What are the exact field names in PCM introspection response? (e.g., `patient` vs `patient_id`, `client_id` vs `clientId`)
- **Context**: Connectathon docs show: `active`, `patient`, `scope`, `client_id`, `consent_id`, `baskets`, `access_type`, `sp_organization_id`, `cnf`, `aud`, `iss`, `iat`, `exp`, `jti`
- **Impact**: Response parsing, DTOs
- **Assumption**: Use snake_case field names as shown in Connectathon spec-python.md
- **Status**: Partially resolved - field names clarified, need confirmation of all optional vs required fields

### Q2.2: Scope Format
- **Question**: Is `scope` a space-separated string, array, or structured FHIR query permissions?
- **Context**: Spec says "ההרשאות יגיעו מנוסחות כשאילתות FHIR מוכנות" (permissions arrive as ready FHIR queries)
- **Impact**: How to forward scopes to FHIR server, whether to parse/validate
- **Assumption**: Space-separated string (OAuth2 standard), forward as-is in internal JWT

### Q2.3: Patient Identifier Type
- **Question**: Is `patient` always a national ID (ת.ז) or passport, or can it be other identifier types?
- **Context**: Need to know the system/coding for ID Replacement lookup
- **Impact**: ID Replacement request format
- **Assumption**: Israeli national ID by default, system from config (`http://fhir.health.gov.il/identifier/israeli-id`)

---

## 3. ID Replacement

### Q3.1: ID Replacement Service Existence
- **Question**: Does an ID Replacement service already exist, or should V1 implement only a mock?
- **Context**: Hebrew spec says "מנגנון זה יפותח כ- service נפרד" (will be developed as separate service). Connectathon docs show endpoint: `POST /api/v1/resolve`
- **Impact**: Whether to build real client or just interface + mock
- **Team**: ID Replacement team to provide endpoint URL and authentication method
- **Assumption**: V1 implements HTTP client interface, use mock for testing until real service available
- **Status**: Pending - need confirmation if service exists and endpoint details

### Q3.4: ID Replacement Authentication
- **Question**: What authentication method does the ID replacement service use?
- **Context**: Connectathon spec shows `Authorization: <from DS_ADAPTER_ID_REPLACEMENT_AUTH>` but doesn't specify format
- **Impact**: Configuration, HTTP client setup
- **Team**: ID Replacement team to provide auth method (Bearer token, Basic auth, API key, mTLS)
- **Status**: Pending - need auth credentials/method from ID Replacement team

### Q3.2: ID Replacement Response Format
- **Question**: Should response include both `localPatientId` (bare ID) and `resourceReference` (full `Patient/id`)?
- **Context**: Different FHIR servers expect different formats in `patient` query param
- **Impact**: Response DTO design, configuration options
- **Assumption**: Return both fields, let adapter config choose which to use

### Q3.3: FHIR Patient Query Format
- **Question**: Should FHIR query use `patient=abc123` (bare ID) or `patient=Patient/abc123` (full reference)?
- **Context**: FHIR R4 spec allows both, servers may vary
- **Impact**: Query construction after ID swap
- **Assumption**: Configurable via `fhir.patientReferenceFormat=bare|full`, default `bare`

---

## 4. Internal JWT

### Q4.1: JWT Subject Claim
- **Question**: Should `sub` be the service provider `client_id` or the local patient ID?
- **Context**: JWT `sub` typically identifies the subject (who/what the token is about)
- **Impact**: FHIR server authorization logic
- **Assumption**: `sub` = service provider `client_id`, `patient` claim = local patient ID (separate claim)

### Q4.2: FHIR Server Expected Claims
- **Question**: What exact JWT claims does the internal FHIR server validate/require?
- **Context**: Connectathon docs show JWT payload with: `iss`, `sub` (local_patient_id), `aud`, `exp`, `iat`, `consent_id`, `scope`, `patient`, `baskets`, `access_type`, `sp_organization_id`, `correlation_id`
- **Impact**: JWT payload structure, validation failures
- **Team**: Internal FHIR team to confirm required vs optional claims
- **Assumption**: Use Connectathon JWT structure as baseline
- **Status**: Partially resolved - structure defined, need FHIR server team confirmation

### Q4.4: Internal FHIR Server URL
- **Question**: What is the exact base URL for the internal FHIR R4 server?
- **Context**: Needed for JWT audience claim and request forwarding
- **Impact**: Configuration, request routing
- **Team**: Internal FHIR team
- **Status**: Pending - need production FHIR server URL

### Q4.3: JWT Expiry
- **Question**: Should JWT expiry be fixed at 60 seconds or configurable?
- **Context**: 60 seconds is aggressive but secure
- **Impact**: Configuration flexibility, FHIR request failures if processing is slow
- **Assumption**: 60 seconds fixed for V1, can make configurable later if needed

---

## 5. FHIR R4 REST Proxy

### Q5.1: FHIR Version Confirmation
- **Clarification**: V1 targets **FHIR R4** over REST requests
- **No FHIR SDK**: Adapter acts as HTTP proxy, parsing JSON directly (no `@types/fhir` or HAPI FHIR client)
- **Impact**: Manual JSON parsing, Bundle structure validation

### Q5.2: HTTP Methods in V1
- **Question**: Confirm V1 supports only GET/search REST requests?
- **Context**: Spec examples show GET, decisions doc says read-only
- **Impact**: Request validation, routing
- **Assumption**: GET only in V1, reject POST/PUT/PATCH/DELETE with 405 Method Not Allowed

### Q5.3: FHIR Bundle Pagination
- **Question**: Should adapter modify `Bundle.link` (next/prev paging URLs) to point back through adapter?
- **Context**: FHIR Bundles include absolute URLs for paging
- **Impact**: URL rewriting, stateful paging
- **Assumption**: V1 passes through paging links unchanged (service provider must re-authenticate for next page)

### Q5.4: FHIR Search Parameters
- **Question**: Are `_include`, `_revinclude`, `_count`, `_sort` allowed in V1?
- **Context**: Common FHIR search params, may affect security (includes pull in related resources)
- **Impact**: Query validation, security review
- **Assumption**: Allow all standard search params, rely on FHIR server + response verification for security

---

## 6. Security / V-label Verification

### Q6.1: Forbidden Security Label Confirmation
- **Question**: Confirm exact system and code for V-labeled resources?
- **Context**: Spec says `http://fhir.health.gov.il/cs/il-core-main-security-label|V`
- **Impact**: Verification logic, config defaults
- **Assumption**: System: `http://fhir.health.gov.il/cs/il-core-main-security-label`, Code: `V`

### Q6.2: Contained Resources
- **Question**: Should verifier inspect `resource.contained[]` (nested resources) for forbidden labels?
- **Context**: FHIR allows contained resources within a resource
- **Impact**: Verification completeness, performance
- **Assumption**: V1 checks only top-level resource and Bundle entries, not `contained[]` (document for future enhancement)

### Q6.3: HTTP Status for Security Violation
- **Question**: Should response be 400 Bad Request, 403 Forbidden, or 500 Internal Server Error when V-label detected?
- **Context**: Want generic error without info leakage
- **Impact**: Client error handling
- **Assumption**: 403 Forbidden with generic OperationOutcome ("Request could not be processed")

---

## 7. Audit / Logging

### Q7.1: Audit Destination in V1
- **Question**: Required audit destination: stdout JSON only, or also file/Kafka/SIEM?
- **Context**: Spec says "internal critical log", V1 scope says stdout
- **Impact**: AuditService implementation complexity
- **Assumption**: Stdout JSON only in V1, make extensible for future targets

### Q7.2: Patient ID Masking
- **Question**: How should patient ID be masked in audit logs (last 4 digits, hashed, fully redacted)?
- **Context**: Balance between auditability and privacy
- **Impact**: Audit event schema, compliance
- **Assumption**: Last 4 digits for national ID (e.g., `****6789`), full hash (SHA-256) available as separate field

### Q7.3: Audit Event Content
- **Question**: Should audit include request path/query params but never response body by default?
- **Context**: Response may contain PHI
- **Impact**: Audit verbosity, compliance risk
- **Assumption**: Include request path/query (no auth header), never log response body in standard audit (only for critical security events, log "V-label detected in X resource type")

---

## 8. Deployment

### Q8.1: Container Strategy
- **Question**: Should V1 include Dockerfile? Kubernetes manifests?
- **Context**: V1 scope says no K8s, but Docker useful for local dev
- **Impact**: Deployment docs, testing
- **Assumption**: Provide Dockerfile for V1, defer K8s manifests

### Q8.2: Secrets Management
- **Question**: Where will secrets (private keys, certs) come from in different environments?
- **Context**: Local dev vs. staging vs. prod. Connectathon uses file paths for certificates.
- **Impact**: Configuration loading, security
- **Assumption**: Local: file paths; Staging/Prod: env vars populated by secret manager (AWS Secrets Manager, K8s secrets, etc.)

### Q8.3: Node.js Version
- **Question**: Require Node.js 20 LTS or 22 (latest)?
- **Context**: Long-term support vs. latest features
- **Impact**: Deployment targets, Docker base image
- **Assumption**: Node.js 20 LTS (active until 2026-04-30), document minimum version in README

---

## 9. Certificate and Trust Management

### Q9.1: PCM CA Certificate
- **Question**: Is the PCM CA certificate required for verifying PCM server's TLS certificate, or does the system CA bundle suffice?
- **Context**: Connectathon docs provide CA cert in bundle download. May be custom CA for PCM infrastructure.
- **Impact**: mTLS client configuration, trust store setup
- **Team**: PCM team + Certificate team
- **Status**: Pending - need clarification if custom CA is required

### Q9.2: Certificate Rotation
- **Question**: What is the certificate rotation policy and procedure?
- **Context**: Client certificates have expiry dates, need process for renewal
- **Impact**: Operational procedures, downtime windows
- **Team**: Certificate team + PCM team
- **Status**: Pending - need certificate lifecycle procedures

### Q9.3: CNF Thumbprint Validation
- **Question**: Should the adapter strictly enforce CNF (certificate confirmation) thumbprint matching, or log warnings only?
- **Context**: Connectathon spec shows CNF validation with `x5t#S256` but says "warning only". Bundle provides thumbprint: `2-mGHGuZkYLdh6YgnoP3-trBcBJbqOGXjobtjI_sRxM`
- **Impact**: Security posture, OAuth2 DPoP-style binding
- **Team**: Security team + PCM team
- **Assumption**: V1 logs warning only, can enable strict mode via configuration flag
- **Status**: Partially resolved - warning mode for V1

### Q9.4: Client Assertion Key vs mTLS Key
- **Question**: Should `PCM_CLIENT_ASSERTION_PRIVATE_KEY_PATH` use the same key as `PCM_MTLS_KEY_PATH`?
- **Context**: Connectathon bundle provides only one private key. Both fields currently point to the same `.key` file.
- **Impact**: Key management complexity, security separation of concerns
- **Team**: PCM team + Security team
- **Assumption**: Connectathon uses same key for both purposes; production may separate them
- **Status**: Pending - confirm approach for Connectathon and production environments

### Q9.5: Root CA Certificate Requirement
- **Question**: Is `rootCA.crt` required by Node.js HTTPS agent for PCM endpoint verification?
- **Context**: Connectathon bundle includes `rootCA.crt`. Node.js typically trusts system CA bundle, but custom PCM CA may be needed.
- **Impact**: mTLS client configuration, TLS verification behavior
- **Team**: PCM team + Infrastructure team
- **Assumption**: Use `PCM_CA_CERT_PATH` if provided, otherwise rely on system CA bundle
- **Status**: Pending - test PCM connection to determine if custom CA is required

### Q9.6: Certificate Thumbprint Storage
- **Question**: Should `PCM_CLIENT_CERT_THUMBPRINT` be stored in config/env, or computed at runtime from the certificate file?
- **Context**: Connectathon bundle provides thumbprint in `bundle.json`. Could also compute from cert file.
- **Impact**: Configuration complexity, consistency with PCM registration
- **Team**: PCM team
- **Assumption**: Store in env var for V1 (easier debugging, matches bundle), can compute at runtime in future
- **Status**: Pending - confirm preferred approach

### Q9.7: Connectathon Key Type Expectations
- **Question**: What key types (RSA vs EC) should we expect from Connectathon certificate bundles?
- **Context**: Implementation supports both ES256 (EC P-256) and RS256 (RSA) via `PCM_CLIENT_ASSERTION_ALGORITHM` config. Connectathon bundle observed with RSA key, but spec examples show ES256.
- **Impact**: Default configuration for Connectathon environment, documentation clarity
- **Team**: PCM team / Connectathon organizers
- **Status**: **RESOLVED for current Connectathon** - The Connectathon certificate bundle provides RSA keys, so `PCM_CLIENT_ASSERTION_ALGORITHM=RS256` is required. `.env.connectathon.example` now reflects this.
- **Finding**: Local Connectathon run confirmed RSA key type. Service logs: "Validated key compatibility: rsa key with RS256 algorithm"
- **Mitigation**: Added `npm run cert:check` diagnostic to detect key type and validate algorithm compatibility

### Q9.8: Production Key Type Requirements
- **Question**: For production environments, does PCM require ES256 (EC) keys, or are both ES256 and RS256 acceptable?
- **Context**: ES256 is more modern and efficient, but RSA (RS256) may be required for compatibility with existing PKI infrastructure
- **Impact**: Certificate issuance process, key generation procedures
- **Team**: PCM team + Certificate team + Security team
- **Status**: Pending - need guidance on production key type requirements
- **Mitigation**: Implementation supports both algorithms via configuration

### Q9.9: Connectathon TLS Certificate SAN
- **Question**: Why does the Connectathon PCM certificate use "pcm-core" as Subject Alternative Name instead of the ELB hostname?
- **Context**: `PCM_BASE_URL` points to `pcm-connectathon-mtls-*.elb.il-central-1.amazonaws.com:4501`, but the server certificate is issued for `DNS:pcm-core, DNS:localhost, IP Address:127.0.0.1`, causing TLS hostname verification failure.
- **Impact**: Requires TLS servername override (`PCM_TLS_SERVERNAME=pcm-core`) to use SNI for correct certificate validation
- **Team**: PCM team / Connectathon organizers
- **Status**: **RESOLVED for current Connectathon** - Added `PCM_TLS_SERVERNAME` config option. Connectathon requires `PCM_TLS_SERVERNAME=pcm-core` to match certificate SAN. `.env.connectathon.example` now includes this.
- **Finding**: Local Connectathon run failed with "Hostname/IP does not match certificate's altnames" until servername override was added
- **Security**: `rejectUnauthorized` remains `true` - certificate is still validated, just using the correct name

### Q9.10: Production PCM Certificate SAN Coverage
- **Question**: Will production PCM certificates include the external hostname (URL) in their Subject Alternative Name?
- **Context**: Production PCM may use load balancers or proxies with different hostnames than certificate SANs, similar to Connectathon ELB setup
- **Impact**: Whether production will require `PCM_TLS_SERVERNAME` override or can rely on hostname matching
- **Team**: PCM team + Infrastructure team + Certificate team
- **Status**: Pending - need production PCM certificate details and whether TLS servername override will be needed
- **Assumption**: Production certificates should include external hostname in SAN to avoid servername override requirement

---

## Status Legend
- **Pending**: Needs external clarification
- **Assumption**: Working assumption for V1, document for review
- **Resolved**: Decision made and documented
