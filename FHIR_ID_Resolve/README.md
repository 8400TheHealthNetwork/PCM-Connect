# FHIR ID Resolve API

Standalone FastAPI service for resolving a national identifier to a local patient ID.

## Endpoint

- `POST /api/v1/resolve`
- Protected with HTTP Basic authentication (configured in `config.json`)

Request body:

```json
{
  "national_id": {
    "system": "http://fhir.health.gov.il/identifier/il-national-id",
    "value": "000000018"
  }
}
```

Success response (`200`):

```json
{
  "patient_id": "12345",
  "resource_reference": "Patient/12345"
}
```

Not found response (`404`):

```json
{
  "error": "patient_not_found",
  "message": "No patient was found for the provided national identifier"
}
```

Service unavailable response (`503`):

```json
{
  "error": "service_unavailable",
  "message": "Unable to reach FHIR server: ..."
}
```

## Configuration

Set values in `config.json`:

- `api.host`, `api.port`: bind configuration
- `auth.username`, `auth.password`: HTTP Basic credentials
- `fhir.base_url`: FHIR server base URL
- `fhir.timeout_seconds`: request timeout
- `fhir.verify_ssl`: verify TLS certificates
- `fhir.default_headers`: optional headers sent to FHIR server
- `resolver.patient_id_strategy`: `resource_id` or `identifier`
- `resolver.patient_id_identifier_system`: required when strategy is `identifier`

You can reference environment variables in config values with `${ENV:VARIABLE_NAME}`.
Example:

```json
{
  "Authorization": "Basic ${ENV:FHIR_TESTSERVER_BASIC_TOKEN}"
}
```

Optional: set `FHIR_RESOLVE_CONFIG` to use a different config path.

## Run

```powershell
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Run as Docker service

Use [config.docker.json](config.docker.json) for container runtime settings.

```powershell
# Base64 token for _SYSTEM:SYS (required when upstream IRIS requires Basic auth)
$env:FHIR_TESTSERVER_BASIC_TOKEN = "X1NZU1RFTTpTWVM="

# Build and start service
docker compose up -d --build

# Follow logs
docker compose logs -f fhir-id-resolve
```

Manual call:

```powershell
$token = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("resolver_user:change-me"))
$headers = @{ Authorization = "Basic $token" }
$body = @{ national_id = @{ system = "http://fhir.health.gov.il/identifier/il-national-id"; value = "000000019" } } | ConvertTo-Json -Compress
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/resolve" -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

Stop service:

```powershell
docker compose down
```

## Run tests

```powershell
pytest -q
```

## Run integration test against FHIR_TestServer

```powershell
# Base64 token for superuser:SYS
$env:FHIR_TESTSERVER_BASIC_TOKEN = "c3VwZXJ1c2VyOlNZUw=="
$env:RUN_FHIR_TESTSERVER_INTEGRATION = "1"
pytest -q -m integration tests/test_integration_fhir_testserver.py
```

Configured IRIS FHIR endpoint:

- `https://iris.intersystemsisrael.com/csp/healthshare/fhir1/fhir/r4`

Known patient resource IDs used by integration checks:

- `Patient/17`
- `Patient/18`
- `Patient/19`
- `Patient/20`
- `Patient/21`
- `Patient/il-hdp-pT-DUP-456789015`
- `Patient/il-hdp-pT-DUP-345678904-inactive`

## Manual tests

```powershell
# Replace credentials and payload values for your environment.
curl -u resolver_user:change-me -X POST http://localhost:8000/api/v1/resolve ^
  -H "Content-Type: application/json" ^
  -d "{\"national_id\":{\"system\":\"http://fhir.health.gov.il/identifier/il-national-id\",\"value\":\"000000018\"}}"
```
