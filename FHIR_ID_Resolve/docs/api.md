# FHIR ID Resolve — API Reference

Version: 1.0.0  
Base URL: `/api/v1`

---

## Authentication

All endpoints require **HTTP Basic Authentication**.

Credentials are configured via the application configuration file (`config.json` or the file pointed to by `FHIR_RESOLVE_CONFIG`).

```
Authorization: Basic <base64(username:password)>
```

---

## Endpoints

### POST /api/v1/resolve

Resolves a national identifier to a local FHIR Patient resource ID.

#### Request

**Content-Type:** `application/json`

| Field | Type | Required | Description |
|---|---|---|---|
| `national_id.system` | string | Yes | The identifier system URI (e.g., `http://fhir.health.gov.il/identifier/il-national-id`) |
| `national_id.value` | string | Yes | The identifier value (e.g., national ID number) |

**Example:**

```json
{
  "national_id": {
    "system": "http://fhir.health.gov.il/identifier/il-national-id",
    "value": "123456789"
  }
}
```

#### Responses

##### 200 OK — Patient Found

```json
{
  "patient_id": "12345",
  "resource_reference": "Patient/12345"
}
```

| Field | Type | Description |
|---|---|---|
| `patient_id` | string | The resolved local patient identifier |
| `resource_reference` | string | FHIR resource reference in the format `Patient/{id}` |

##### 401 Unauthorized — Invalid Credentials

Returned when Basic Auth credentials are missing or incorrect.

```
WWW-Authenticate: Basic
```

##### 404 Not Found — No Patient Matched

```json
{
  "error": "patient_not_found",
  "message": "No patient was found for the provided national identifier"
}
```

##### 409 Conflict — Multiple Active Patients

Returned when more than one active Patient resource matches the given identifier.

```json
{
  "error": "duplicate_active_patient",
  "message": "More than one active patient was found for the provided national identifier",
  "patient_ids": ["12345", "67890"]
}
```

##### 503 Service Unavailable — Upstream FHIR Server Error

Returned when the upstream FHIR server is unreachable or returns an error.

```json
{
  "error": "service_unavailable",
  "message": "Unable to reach FHIR server: <details>"
}
```

---

## Resolution Logic

1. The service queries the configured FHIR server: `GET /Patient?identifier={system}|{value}`
2. Filters results to only **active** Patient resources (where `active` is `true` or absent).
3. If no active patients are found → `404`.
4. If more than one active patient is found → `409`.
5. Extracts the patient ID based on the configured strategy:
   - `resource_id` — uses the FHIR resource `id` field.
   - `identifier` — uses the value from a specific identifier system (`patient_id_identifier_system`), falling back to `resource_id` if not found.

---

## Configuration

Configuration is loaded from a JSON file. The path defaults to `config.json` and can be overridden with the `FHIR_RESOLVE_CONFIG` environment variable.

Environment variable placeholders (`${ENV:VAR_NAME}`) are supported in configuration values.

### Configuration Schema

```json
{
  "api": {
    "host": "0.0.0.0",
    "port": 8000
  },
  "auth": {
    "username": "<basic-auth-username>",
    "password": "<basic-auth-password>"
  },
  "fhir": {
    "base_url": "http://fhir-server:52773/fhir/r4",
    "timeout_seconds": 10.0,
    "verify_ssl": true,
    "default_headers": {}
  },
  "resolver": {
    "patient_id_strategy": "resource_id",
    "patient_id_identifier_system": null
  }
}
```

| Section | Field | Type | Default | Description |
|---|---|---|---|---|
| `api` | `host` | string | `0.0.0.0` | Bind address |
| `api` | `port` | int | `8000` | Listen port |
| `auth` | `username` | string | — | Basic Auth username (required) |
| `auth` | `password` | string | — | Basic Auth password (required) |
| `fhir` | `base_url` | string | — | Upstream FHIR server base URL (required) |
| `fhir` | `timeout_seconds` | float | `10.0` | HTTP timeout for FHIR requests |
| `fhir` | `verify_ssl` | bool | `true` | Whether to verify TLS certificates |
| `fhir` | `default_headers` | object | `{}` | Additional headers sent to the FHIR server |
| `resolver` | `patient_id_strategy` | string | `resource_id` | `resource_id` or `identifier` |
| `resolver` | `patient_id_identifier_system` | string | `null` | Required when strategy is `identifier` |

---

## Error Response Format

All error responses follow a consistent structure:

```json
{
  "error": "<error_code>",
  "message": "<human-readable description>"
}
```

The `409` response additionally includes a `patient_ids` array.
