# DS Adapter (Python / FastAPI)

Stateless Policy Enforcement Point that proxies FHIR requests through:
PCM token introspection → ID replacement → internal JWT minting → FHIR forward
→ response verification → audit.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn src.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health   # → {"status":"ok"}
```

## Run tests

```bash
.venv/bin/pytest tests -v
```

Unit tests: `tests/unit/`. Integration tests (full flow with respx mocks for
PCM / ID / FHIR): `tests/integration/`.

## Configuration

Defaults live in `config.yaml`. Override any field with an env var:
`DS_ADAPTER_<SECTION>_<FIELD>` (uppercase). Nested fields collapse with
underscores, e.g.

```bash
DS_ADAPTER_PCM_BASE_URL=https://pcm.example
DS_ADAPTER_FHIR_SERVER_TIMEOUT_SECONDS=10
DS_ADAPTER_AUDIT_TARGETS_FILE_PATH=/tmp/audit.log
```

### Required secrets (env vars)

| Variable | Purpose |
|----------|---------|
| `DS_ADAPTER_JWT_SIGNING_KEY` | PEM ES256 private key for minting internal JWTs |
| `DS_ADAPTER_PCM_CLIENT_KEY` | PEM key for PCM client_assertion signing |
| `DS_ADAPTER_PCM_CLIENT_CERT` | PEM cert path (mTLS) |
| `DS_ADAPTER_PCM_CA_CERT` | PEM CA path (mTLS) |
| `DS_ADAPTER_ID_REPLACEMENT_AUTH` | Auth header value for the org's ID resolver |

## Endpoints

| Path | Method | Purpose |
|------|--------|---------|
| `/fhir/{path}` | GET/POST/PUT/DELETE/PATCH | Proxied FHIR call (Bearer required) |
| `/health` | GET | Liveness — always 200 if process is up |
| `/ready` | GET | Probes PCM + FHIR; 200 ready / 503 not_ready |
| `/metrics` | GET | Prometheus exposition |

## Error catalog

Every error returns a FHIR `OperationOutcome` with a stable code under
`http://ds-adapter/error-codes` (see `src/errors/catalog.py`). HTTP status
mirrors the catalog: `AUTH_001 → 401`, `ID_002 → 404`, `FHIR_002 → 504`, etc.

## Docker

```bash
docker compose up --build
curl http://localhost:8000/health
```

The compose file boots the adapter alongside two `mockserver` instances
acting as PCM and FHIR. Configure expectations against them via the
mockserver REST API on ports 3000 and 8080.

## Project layout

```
src/
  main.py              # app factory + lifespan
  api/                 # routes + dependencies
  auth/                # PCM client, JWT, mTLS, CNF
  identity/            # ID replacement
  fhir/                # FHIR client + verification
  audit/               # service, formatters, targets
  errors/              # catalog, models, handlers
  middleware/          # correlation, timing, audit
  observability/       # OTel + Prometheus metrics
  logging/             # structlog setup
  config/              # Pydantic models + YAML loader
tests/
  unit/                # per-module
  integration/         # full flow with respx
```
