# PCM Connect (DS-Adapter) — API Reference

Version: 1.0.0  
Base URL: `/`

---

## Authentication

### FHIR Proxy Endpoint

The `/fhir/{path}` endpoint requires a **Bearer token** in the `Authorization` header. The token is a PCM-issued access token that will be introspected against the PCM introspection endpoint.

```
Authorization: Bearer <pcm-access-token>
```

### Discovery & Operational Endpoints

The `.well-known/*`, `/health`, `/ready`, and `/metrics` endpoints are **unauthenticated**.

---

## Endpoints

### GET /health

Liveness probe. Confirms the process is alive.

#### Response

**200 OK**

```json
{
  "status": "ok"
}
```

---

### GET /ready

Readiness probe. Validates connectivity to dependent services (FHIR server, PCM).

#### Response

**200 OK** — All dependencies reachable:

```json
{
  "status": "ready",
  "fhir_server": "ok",
  "pcm": "ok"
}
```

**503 Service Unavailable** — One or more dependencies unreachable:

```json
{
  "status": "not_ready",
  "fhir_server": "ok",
  "pcm": "error"
}
```

---

### GET /metrics

Prometheus metrics endpoint. Returns metrics in Prometheus text exposition format.

**Content-Type:** `text/plain; version=0.0.4; charset=utf-8`

Exposed metrics include:
- HTTP request count (by method, path, status code)
- PCM introspection duration (histogram)
- ID replacement duration (histogram)
- FHIR forward duration (histogram)

---

### GET /.well-known/jwks.json

Returns the JSON Web Key Set (JWKS) containing the adapter's public signing key. Used by the FHIR server to verify JWTs issued by this adapter.

#### Response

**Content-Type:** `application/jwk-set+json`

```json
{
  "keys": [
    {
      "kty": "EC",
      "kid": "<key-id>",
      "use": "sig",
      "alg": "ES256",
      "crv": "P-256",
      "x": "...",
      "y": "..."
    }
  ]
}
```

---

### GET /.well-known/oauth-authorization-server

OAuth 2.0 Authorization Server Metadata (RFC 8414). Returns metadata about the adapter's OAuth capabilities.

Returns `404` if metadata is disabled in configuration (`metadata.enabled: false`).

#### Response

**200 OK** — `application/json`

```json
{
  "issuer": "https://ds-adapter.example.com",
  "jwks_uri": "https://ds-adapter.example.com/.well-known/jwks.json",
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "client_credentials"],
  "token_endpoint_auth_methods_supported": ["private_key_jwt"],
  "code_challenge_methods_supported": ["S256"],
  "scopes_supported": ["openid", "patient/*.read", "..."]
}
```

---

### GET /.well-known/openid-configuration

OpenID Connect Discovery metadata.

Returns `404` if metadata is disabled in configuration.

#### Response

Same structure as `/.well-known/oauth-authorization-server` with additional OIDC-specific fields.

---

### GET /.well-known/smart-configuration

SMART on FHIR configuration metadata (SMART App Launch v2).

Returns `404` if metadata is disabled in configuration.

#### Response

**200 OK** — `application/json`

```json
{
  "issuer": "https://ds-adapter.example.com",
  "jwks_uri": "https://ds-adapter.example.com/.well-known/jwks.json",
  "authorization_endpoint": "...",
  "token_endpoint": "...",
  "introspection_endpoint": "...",
  "scopes_supported": ["openid", "launch", "patient/*.read", "..."],
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "client_credentials"],
  "code_challenge_methods_supported": ["S256"],
  "capabilities": ["launch-standalone", "client-public"]
}
```

---

### ANY /fhir/{path}

FHIR reverse proxy. Forwards requests to the configured FHIR server after performing token introspection, patient ID resolution, and JWT minting.

**Supported methods:** `GET`, `POST`, `PUT`, `DELETE`, `PATCH`

#### Request

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer <pcm-access-token>` |
| `X-Correlation-ID` | No | Correlation ID for distributed tracing. Auto-generated if absent. |

The request body and all non-hop-by-hop headers (except `Authorization`) are forwarded to the FHIR server.

#### Processing Flow

1. **Token Introspection** — The PCM access token is introspected against the PCM introspection endpoint to extract patient identity, scope, consent, and baskets.
2. **CNF Validation** — Optional confirmation (`cnf`) claim validation against the client certificate.
3. **Patient ID Resolution** — The PCM patient identifier is resolved to a local FHIR patient ID via the ID Replacement service (FHIR_ID_Resolve).
4. **JWT Minting** — An internal JWT is minted with the resolved patient ID, consent, scope, and baskets. Signed with the adapter's private key.
5. **Forward** — The request is forwarded to the FHIR server with the internal JWT as the `Authorization` header.
6. **Response Verification** — Optionally verifies the FHIR response does not contain forbidden labels.
7. **Return** — The FHIR server response is returned to the caller.

#### Response

The response mirrors the upstream FHIR server response (status code, headers, body).

**Content-Type:** `application/fhir+json` (default)

#### Error Responses

| Status | Code | Description |
|---|---|---|
| 401 | `AUTH_001` | Missing or malformed `Authorization` header |
| 401 | `AUTH_002` | Introspection did not return a patient identifier |
| 500 | `CFG_001` | JWT signing key not configured |
| 503 | — | Upstream FHIR server or ID Replacement service unavailable |

Error response body:

```json
{
  "error": "<error_code>",
  "message": "<human-readable description>"
}
```

---

## Configuration

Configuration is loaded from a YAML file (`config.yaml`) and can be overridden with environment variables prefixed with `DS_ADAPTER_`.

### Key Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DS_ADAPTER_JWT_SIGNING_KEY` | Yes | PEM-encoded private key (or base64-encoded PEM) for JWT signing |
| `DS_ADAPTER_JWT_AUDIENCE` | No | JWT `aud` claim. Comma-separated for multiple values. Defaults to `fhir_server.base_url` |
| `LOG_LEVEL` | No | Logging level (`debug`, `info`, `warning`, `error`). Default: `info` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | OpenTelemetry collector endpoint |

### Configuration Sections

| Section | Description |
|---|---|
| `server` | Bind host, port, shutdown timeout |
| `pcm` | PCM base URL, token/introspect endpoints, mTLS settings |
| `fhir_server` | Upstream FHIR server base URL, protocol, timeout |
| `id_replacement` | ID Replacement service (FHIR_ID_Resolve) URL, endpoint, retries |
| `jwt` | Signing algorithm, issuer, audience, expiry |
| `metadata` | Discovery endpoint configuration (JWKS URI, scopes, capabilities) |
| `audit` | Audit logging targets (syslog, file, Kafka) and format |
| `logging` | Log level and format |
| `otel` | OpenTelemetry tracing configuration |
| `verification` | Response verification (forbidden labels) |

---

## Observability

### Distributed Tracing

The adapter instruments all requests with OpenTelemetry. Trace context is propagated via `traceparent` / `tracestate` headers.

### Audit Logging

Every FHIR proxy request is audit-logged with:
- Correlation ID
- Patient ID
- Scope and consent
- FHIR response status
- Timestamp

Audit logs can be emitted to file, syslog, or Kafka in JSON or CEF format.
