# DS Adapter — Project Plan (Python / FastAPI)

> Implementation plan derived from `spec-python.md`. Organized into incremental phases — each phase produces a runnable, testable artifact.

---

## 0. Overview

**Goal**: Build a stateless Policy Enforcement Point that proxies FHIR requests through PCM token introspection, ID replacement, internal JWT minting, and response verification.

**Strategy**: Vertical-slice incremental delivery. Get a "skeleton" happy path running end-to-end with mocks early, then harden each component (error handling, audit, observability, security).

**Definition of Done (project)**:
- All unit + integration tests pass
- Happy path works against `docker-compose` with mock PCM + FHIR
- All 13 error codes map to correct `OperationOutcome` responses
- Audit + OpenTelemetry + Prometheus metrics emit correctly
- Image builds and runs as non-root, passes healthcheck

---

## 1. Phases at a glance

| Phase | Focus | Outcome |
|-------|-------|---------|
| 1 | Scaffolding & Config | App boots, config loads from YAML+env, `/health` returns 200 |
| 2 | Logging, Correlation, Errors | Structured logs, correlation IDs, OperationOutcome error envelope |
| 3 | PCM Client & JWT | Token acquisition (cached), introspection, ES256 internal JWT minting |
| 4 | ID Replacement | Resolve national → local patient ID with retry |
| 5 | FHIR Forwarding | Proxy requests, inject `_security:not`, return response |
| 6 | Response Verification | Scan responses for forbidden security labels |
| 7 | Audit | File / Kafka / Syslog targets, JSON / CEF formatters |
| 8 | Observability | OpenTelemetry traces + metrics, Prometheus endpoint |
| 9 | Hardening | mTLS modes, graceful shutdown, readiness, security review |
| 10 | Packaging | Dockerfile, docker-compose, README |

---

## 2. Phase 1 — Scaffolding & Configuration

**Goal**: FastAPI app boots from `config.yaml` with env overrides; `/health` returns 200.

### Tasks
- [ ] Create directory layout per spec §3
- [ ] `requirements.txt` — runtime dependencies: FastAPI, uvicorn, httpx, PyJWT, cryptography, pydantic-settings, PyYAML, structlog, aiokafka, opentelemetry-sdk
- [ ] `requirements-dev.txt` — runtime requirements plus pytest, pytest-asyncio, and respx for development and tests
- [ ] `src/config/models.py` — Pydantic models for every section in spec §4.1 (`ServerConfig`, `PCMConfig`, `FHIRConfig`, `IDReplacementConfig`, `JWTConfig`, `AuditConfig` (+ targets), `LoggingConfig`, `OTelConfig`, `VerificationConfig`, root `AppConfig`)
- [ ] `src/config/settings.py` — `load_config()` reads `config.yaml`, applies `DS_ADAPTER_<SECTION>_<KEY>` env overrides, validates → `AppConfig`. On failure raise `ConfigurationError` with code `CFG_001`
- [ ] `src/main.py` — FastAPI app factory, lifespan that loads config and stores it on `app.state.config`
- [ ] `src/api/routes.py` — `GET /health` → `{"status": "ok"}`
- [ ] `config.yaml` — copy defaults from spec §4.1
- [ ] Unit tests: `test_config.py` (load yaml, env override, validation failure)

### Deliverable
`uvicorn src.main:app` boots, `curl localhost:8000/health` → `200 {"status":"ok"}`.

---

## 3. Phase 2 — Logging, Correlation, Errors

**Goal**: Every request gets a correlation ID; every error returns a FHIR `OperationOutcome`.

### Tasks
- [ ] `src/logging/setup.py` — `configure_logging(level)` using structlog. JSON output. INFO+DEBUG → stdout, WARNING+ERROR → stderr (spec §10.3)
- [ ] `src/middleware/correlation.py` — extract `X-Correlation-ID` header or generate uuid4; bind to `request.state.correlation_id` and to structlog contextvars; echo back on response
- [ ] `src/middleware/timing.py` — record start/end, attach `response_time_ms` to `request.state` for downstream audit
- [ ] `src/errors/catalog.py` — `ERROR_CATALOG` dict matching spec §7 (13 codes → status, issue_code, display, diagnostics)
- [ ] `src/errors/models.py` — `build_operation_outcome(code: str) -> dict` per spec §7
- [ ] `src/errors/handlers.py` — `register_exception_handlers(app)`:
  - `DSAdapterError(code)` → mapped status + OperationOutcome
  - Generic `Exception` → 500 / `GEN_001` (no stack trace leakage)
  - Validation/HTTP exceptions wrapped as appropriate
- [ ] `src/api/dependencies.py` — `get_correlation_id`, `get_bearer_token` (raises `AUTH_001` if missing/malformed)
- [ ] Unit tests: `test_error_handlers.py` (each code → correct JSON), `test_correlation.py` (extract / generate / propagate)

### Deliverable
`/health` still works; hitting an unknown route returns proper OperationOutcome; correlation ID round-trips.

---

## 4. Phase 3 — PCM Client & Internal JWT

**Goal**: Acquire & cache PCM access token; introspect SP token; mint signed internal JWT.

### Tasks
- [ ] `src/auth/mtls.py` — `create_mtls_client(pcm_config)` returns `httpx.AsyncClient` with cert/key/CA when `pcm.mtls_client: true`, else plain client (spec §11)
- [ ] `src/auth/pcm_client.py`:
  - `PCMClient` holding shared `httpx.AsyncClient`, in-memory token cache `(access_token, expires_at)`
  - `get_token()` — build ES256 client_assertion JWT (iss/sub=client_id, aud=token_url, exp=now+60, jti=uuid4), POST `client_credentials` with `client_assertion_type=...:jwt-bearer`, parse `{access_token, expires_in}`, cache. On unreachable → `PCM_001`; on auth failure → `PCM_002`
  - `introspect(opaque_token)` — POST introspection endpoint with adapter token; parse `IntrospectionResponse` (Pydantic): `active, patient, scope, consent_id, baskets, access_type, sp_organization_id, cnf{x5t#S256}`. `active=false` → `AUTH_002`; expired → `AUTH_003`
- [ ] `src/auth/jwt_service.py`:
  - `mint_internal_jwt(claims, signing_key)` per spec §5.1 step 9
  - Read `DS_ADAPTER_JWT_SIGNING_KEY` (PEM), sign ES256
- [ ] CNF comparison helper (spec §5.1 step 7) — log WARNING on mismatch, do **not** block
- [ ] Unit tests: `test_pcm_client.py` (success, error, cache hit, cache expiry, introspect active/inactive — using respx), `test_jwt_service.py` (claims, signature roundtrip with public key, expiry)

### Deliverable
Module-level happy path callable from a script; cache behavior verified; signed JWT verifies against its public key.

---

## 5. Phase 4 — ID Replacement

**Goal**: Resolve national ID → local patient ID with retries.

### Tasks
- [ ] `src/identity/id_replacement.py`:
  - `resolve_patient_id(national_id) -> str`
  - POST per spec §16 contract; auth from `DS_ADAPTER_ID_REPLACEMENT_AUTH`
  - Retry loop: `id_replacement.retries` times with `retry_backoff_seconds`
  - 200 → return `patient_id`; 404 → raise `ID_002` (no retry); timeout/5xx/connection → retry; all retries failed → `ID_001`
- [ ] Unit tests: `test_id_replacement.py` (success, 404, timeout+retry success, all retries fail, retry count + backoff verified)

### Deliverable
Resolver works against respx mock; retry semantics verified.

---

## 6. Phase 5 — FHIR Forwarding (Happy Path End-to-End)

**Goal**: First end-to-end vertical slice — proxy a real GET through every step.

### Tasks
- [ ] `src/fhir/client.py` — `forward_to_fhir(method, path, query, headers, body)`. Build URL from `fhir_server.base_url`, attach `Authorization: Bearer <internal_jwt>` and `X-Correlation-ID`. Timeout → `FHIR_002`; connection error → `FHIR_001`
- [ ] `src/api/routes.py` — catch-all `{METHOD} /fhir/{path:path}`:
  1. extract bearer (`AUTH_001` if missing)
  2. `pcm_client.get_token()` → `pcm_client.introspect(token)`
  3. CNF compare (warn only)
  4. `id_replacement.resolve(introspection.patient)`
  5. `jwt_service.mint(...)` with all claims
  6. `fhir.client.forward(...)` (request forwarded as-is — no query rewriting in this stage)
  7. return response (status, body, `Content-Type: application/fhir+json`, `X-Correlation-ID`)
- [ ] Wire dependencies via FastAPI `Depends` (singletons stored on `app.state` in lifespan)
- [ ] Integration test: `test_happy_path.py` (mock PCM + ID + FHIR → 200 with Bundle)

### Deliverable
Full happy path works against respx mocks; integration test green.

---

## 7. Phase 6 — Response Verification

**Goal**: Defense-in-depth scan for forbidden security labels.

### Tasks
- [ ] `src/fhir/verification.py` — `verify_response(body, config) -> bool`
  - If `verification.enabled == false` → pass
  - Parse JSON; if `resourceType == "Bundle"` walk `entry[].resource.meta.security`; else walk `meta.security`
  - For each coding build `"system|code"` and compare against `forbidden_labels`
  - Match → log CRITICAL, write audit `severity=critical`, return failure
- [ ] Wire into route handler between forward and return — on failure return 400 with **generic** OperationOutcome (no label leakage; spec §5.1 step 12)
- [ ] Unit tests: `test_verification.py` (no labels pass, V label fails, single resource fails, disabled skips, empty bundle passes, malformed body)
- [ ] Integration test: `test_verification_failures.py` (forbidden label → 400)

### Deliverable
Forbidden labels caught; clean responses pass through.

---

## 8. Phase 7 — Audit

**Goal**: Every request audited (success + failure); audit failure must never fail a request.

### Tasks
- [ ] `src/audit/formatters/json_fmt.py` — record per spec §8.2 (timestamp, correlation_id, source_ip, method, path, fhir_scope, masked patient_id, sp_organization_id, consent_id, response_status, response_time_ms, error)
- [ ] `src/audit/formatters/cef_fmt.py` — CEF format
- [ ] Patient ID masking helper (last 4 digits)
- [ ] `src/audit/targets/file.py` — append JSON lines, daily rotation, retain `max_files`
- [ ] `src/audit/targets/kafka.py` — `aiokafka` producer, fire-and-forget
- [ ] `src/audit/targets/syslog.py` — RFC 5424, UDP/TCP, facility LOCAL0
- [ ] `src/audit/service.py` — `AuditService.record(audit_record)` dispatches to all enabled targets concurrently; wraps each in try/except (log WARNING on failure, never raise)
- [ ] `src/middleware/audit_middleware.py` — capture request metadata; on response (success or error), build record and call `AuditService.record(...)`. Pulls patient_id / scope / consent_id / sp_organization_id from `request.state` (set by route handler)
- [ ] Tests: per-target unit tests; integration test verifies audit emitted on both success and failure paths

### Deliverable
Audit lines in `/var/log/adapter/audit.log` for every test request; killing the file path doesn't break the request.

---

## 9. Phase 8 — Observability

**Goal**: OpenTelemetry traces + metrics, Prometheus endpoint.

### Tasks
- [ ] `src/observability/setup.py` — `init_otel(app, config)`:
  - OTLP exporter at `otel.endpoint`, service name, sample rate
  - Auto-instrument FastAPI + httpx
  - Manual spans per spec §9.1: `pcm.token_acquire`, `pcm.introspect`, `id.replacement`, `jwt.mint`, `fhir.forward`, `fhir.verify` — wrap each call site
- [ ] Metrics per spec §9.2 (Counter / Histogram) — increment / observe at appropriate points
- [ ] `GET /metrics` endpoint exposing Prometheus text format
- [ ] Smoke test: traces visible in OTLP collector container; `/metrics` lists every metric

### Deliverable
Spans + metrics emitted; counters/histograms populated under load.

---

## 10. Phase 9 — Hardening: Errors, Readiness, Shutdown, Security

**Goal**: All error paths covered; readiness reflects dependencies; clean shutdown.

### Tasks
- [ ] `GET /ready` — concurrent HEAD probes to `fhir_server.base_url` and `pcm.base_url` (5s timeout each); 200 if both ok, 503 otherwise (spec §6.3)
- [ ] Verify every error code from spec §5.2 has a test:
  - AUTH_001 / AUTH_002 / AUTH_003
  - PCM_001 / PCM_002
  - ID_001 / ID_002
  - FHIR_001 / FHIR_002
  - Verification failure → 400
  - GEN_001 catch-all
  - CFG_001 startup failure
- [ ] Integration test files: `test_auth_failures.py`, `test_id_failures.py`, `test_fhir_failures.py`
- [ ] Graceful shutdown handler (spec §15): stop accepting → drain in-flight (`shutdown_timeout_seconds`) → flush audit file → close Kafka producer → close httpx clients
- [ ] Security review checklist (spec §17):
  - No secrets in code or config — only env vars
  - No stack traces in responses
  - Patient ID masked in audit (last 4 digits)
  - cnf mismatch is WARNING-only
  - Audit failures wrapped, log only

### Deliverable
All 13 error codes covered by tests; service shuts down cleanly under SIGTERM.

---

## 11. Phase 10 — Packaging & Docs

**Goal**: Reproducible local + container deployment.

### Tasks
- [ ] `Dockerfile` per spec §12 — non-root `appuser`, healthcheck, slim base
- [ ] `docker-compose.yaml` per spec §13 — adapter + mock-pcm + mock-fhir, certs + config mounted
- [ ] Generate self-signed certs script for local dev (mTLS + JWT signing key)
- [ ] `README.md` — quick start, env var reference, config reference, troubleshooting
- [ ] Verify: `docker compose up` → happy-path `curl` returns 200

### Deliverable
Fresh checkout → `docker compose up` → working service in <2 minutes.

---

## 12. Module → Phase mapping

| Module | Phase introduced |
|--------|------------------|
| `config/` | 1 |
| `logging/`, `middleware/correlation.py`, `middleware/timing.py`, `errors/` | 2 |
| `auth/` | 3 |
| `identity/` | 4 |
| `fhir/client.py`, `api/routes.py` (full route) | 5 |
| `fhir/verification.py` | 6 |
| `audit/`, `middleware/audit_middleware.py` | 7 |
| `observability/`, `/metrics` | 8 |
| `/ready`, shutdown | 9 |
| `Dockerfile`, `docker-compose.yaml`, `README.md` | 10 |

---

## 13. Risks & open questions

| Topic | Question / Risk | Resolution path |
|-------|-----------------|-----------------|
| Token cache | Per-process in-memory only — multiple workers each fetch separately. Spec is silent. | Document; revisit if PCM rate-limits |
| `consent_id` on AUTH_004 (403) | Spec §7 lists `AUTH_004` but flow §5.2 doesn't trigger it | Confirm with spec owner whether consent-scope checks are in scope |
| ID Replacement auth header format | `DS_ADAPTER_ID_REPLACEMENT_AUTH` is "org-specific" — Bearer? Basic? raw? | Confirm or make pluggable |
| Daily file rotation | Stdlib `TimedRotatingFileHandler` rotates by writer time — fine for single process; multi-worker writers will race | Use one writer process or external rotation (logrotate) |
| OTel + Prometheus together | OTel SDK exposes metrics via OTLP; Prometheus scrape needs Prom exporter | Use `opentelemetry-exporter-prometheus` and mount on `/metrics` |

---

## 14. Test coverage matrix (target)

| Layer | Files | Required scenarios |
|-------|-------|--------------------|
| Unit | `test_config.py`, `test_pcm_client.py`, `test_jwt_service.py`, `test_id_replacement.py`, `test_verification.py`, `test_error_handlers.py`, `test_correlation.py` | Per spec §14.1 |
| Integration | `test_happy_path.py`, `test_auth_failures.py`, `test_id_failures.py`, `test_fhir_failures.py`, `test_verification_failures.py` | Per spec §14.2 |
| Fixtures | `conftest.py` | `app`, `client`, `mock_pcm`, `mock_fhir`, `mock_id_service`, `sample_introspection_response`, `sample_fhir_bundle`, `sample_fhir_bundle_with_v_label`, `es256_keypair` |

---

## 15. Suggested execution order (first PRs)

1. **PR-1** — Phase 1 scaffolding (boots, `/health`, config tests pass)
2. **PR-2** — Phase 2 logging + correlation + error envelope
3. **PR-3** — Phase 3 PCM client + JWT service (unit-tested in isolation)
4. **PR-4** — Phase 4 ID replacement
5. **PR-5** — Phase 5 wire happy path end-to-end + integration test
6. **PR-6** — Phase 6 verification
7. **PR-7** — Phase 7 audit (file target first; Kafka/syslog can follow)
8. **PR-8** — Phase 8 observability
9. **PR-9** — Phase 9 readiness + remaining error coverage + shutdown
10. **PR-10** — Phase 10 Docker + compose + README

Each PR should ship green tests and be independently mergeable.
