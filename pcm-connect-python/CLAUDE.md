# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this service is

A stateless FHIR Policy Enforcement Point (PEP) implemented as a FastAPI proxy. Every `/fhir/{path}` request flows through a fixed pipeline:

1. Extract Bearer (`AUTH_001` if missing)
2. `PCMClient.introspect(token)` — connectathon PCM uses `private_key_jwt` (each introspect call carries its own signed `client_assertion`), not the spec's bearer flow. See `src/auth/pcm_client.py`.
3. CNF (`x5t#S256`) compare — **WARNING-only, never blocks** (`src/auth/cnf.py`).
4. `IDReplacementClient.resolve_patient_id(introspection.patient)` — national ID → local patient ID, with retry loop (`ID_001`/`ID_002`).
5. `mint_internal_jwt(...)` — ES256, signed with `DS_ADAPTER_JWT_SIGNING_KEY` (separate from PCM mTLS key).
6. `FHIRClient.forward(...)` — proxies as-is. Inbound `Authorization` and `X-Correlation-ID` are stripped and replaced; hop-by-hop headers filtered both directions (`_HOP_BY_HOP` in `src/api/routes.py`).
7. `ResponseVerifier.verify(...)` — scans `meta.security` (Bundle entries or single resource) for `forbidden_labels`. Match → `VRF_001` with **generic** OperationOutcome; do not leak the matching label.

Wiring is in `src/main.py` (lifespan); HTTP clients (`pcm_http`, `id_http`, `fhir_http`) are singletons on `app.state` and closed at shutdown.

## Common commands

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn src.main:app --reload
.venv/bin/pytest tests -v
.venv/bin/pytest tests/unit/test_pcm_client.py::test_name -v   # single test
docker compose up --build                                        # adapter + mockserver PCM + mockserver FHIR
```

`pyproject.toml` sets `asyncio_mode = "auto"` — async tests don't need `@pytest.mark.asyncio`. All HTTP mocking uses `respx`. Reusable `es256_keypair` fixture is in `tests/conftest.py`; integration fixtures are in `tests/integration/conftest.py`.

## Configuration model

`config.yaml` is the source of defaults. Every leaf field can be overridden by an env var named `DS_ADAPTER_<SECTION>_<FIELD>` (uppercase, underscore-joined). Overrides are applied **schema-driven** by walking the Pydantic models — there is no string parsing, so underscores within field names are unambiguous (e.g. `fhir_server.base_url` → `DS_ADAPTER_FHIR_SERVER_BASE_URL`). See `src/config/settings.py:_apply_env_overrides`.

All config models in `src/config/models.py` use `extra="forbid"` — adding a new field to YAML or env without updating the model raises `CFG_001` at startup.

Required env-only secrets (never in YAML):

| Variable | Purpose |
|---|---|
| `DS_ADAPTER_JWT_SIGNING_KEY` | PEM ES256 private key for internal JWT minting |
| `DS_ADAPTER_PCM_CLIENT_KEY` | PEM key for `client_assertion` signing |
| `DS_ADAPTER_PCM_CLIENT_CERT` | PEM cert path (mTLS) |
| `DS_ADAPTER_PCM_CA_CERT` | PEM CA path (mTLS) |
| `DS_ADAPTER_ID_REPLACEMENT_AUTH` | Auth header value for the ID resolver (org-specific) |
| `DS_ADAPTER_CLIENT_ID` | OAuth `clientId` — used as `iss`/`sub` of the client_assertion |
| `DS_ADAPTER_PCM_TOKEN_RESOURCE` | Optional RFC 8707 resource indicator on `/token` |

`_load_pem` in `src/main.py` accepts either a PEM blob or a file path — keep that flexibility when adding new key inputs.

## Errors

Every error is a FHIR `OperationOutcome` with a stable code under `http://ds-adapter/error-codes`. The catalog (`src/errors/catalog.py`) is the single source of truth: code → HTTP status, FHIR `issue_code`, display, diagnostics. Throw `DSAdapterError(msg, code="XXX_NNN")`; the registered handler maps it. Generic exceptions become `GEN_001` (no stack-trace leakage). Verification failure (`VRF_001`) returns 400 with **generic** wording — do not include the offending label.

## Auditing

`AuditMiddleware` (outermost user middleware after correlation/timing) captures every request and dispatches the record concurrently to all enabled targets in `src/audit/targets/` (file/kafka/syslog). Per-target failures are caught and logged — **audit failures must never fail a request**. The middleware reads `request.state.local_patient_id`, `fhir_scope`, `consent_id`, `sp_organization_id`, `fhir_status` set by the route handler. Patient IDs are masked to last-4 in audit output.

## Observability

OTel auto-instrumentation for FastAPI + httpx is enabled in `init_otel`. Manual spans wrap the four pipeline calls — keep instrumentation at call sites in `src/api/routes.py` consistent (currently per-step `metrics.*_DURATION.observe(...)`). `/metrics` returns Prometheus text; `/health` is unconditional 200; `/ready` does HEAD probes against `pcm.base_url` and `fhir_server.base_url` (5s timeout each, 503 if either fails).

## Connectathon-specific gotchas

- `pcm.verify_hostname: false` is intentional — the connectathon ELB's cert is `CN=pcm-core` and the SAN doesn't match the ELB hostname; the chain is still verified against `rootCA.crt`.
- `pcm.introspect_auth_method: private_key_jwt` is the connectathon flow. The "spec default" `bearer` flow (acquire adapter token via `client_credentials`, then `Authorization: Bearer` on introspect) still exists in `PCMClient.get_token()` and is used when `introspect_auth_method: bearer`.
- The PCM may return non-2xx with a valid `{active: false}` introspection body — `PCMClient.introspect` parses the body **before** checking status, and only treats responses missing the `active` field as transport/auth failures (`PCM_001`/`PCM_002`).

## Don'ts

- Don't put secrets in `config.yaml` — env-only, see table above.
- Don't add stack traces to error responses; never include the matching forbidden label in `VRF_001` output.
- Don't make CNF mismatch fail the request — it's WARNING-only by design.
- Don't add a new top-level config section without updating `AppConfig` (extra="forbid").
- Don't bypass the schema-driven env override walker by parsing env var names — extend the Pydantic model and the walker handles it.
