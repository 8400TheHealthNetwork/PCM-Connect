# Audit logging

PCM Connect emits a security audit event for every request handled by the
`/fhir` proxy. Audit events are separate from application logs and
OpenTelemetry traces, but ECS events include identifiers that can correlate all
three signals.

The audit implementation is platform-neutral. Events can be sent to stdout, a
file, syslog, or Kafka. ECS output is suitable for Elastic and other collectors
that accept structured JSON. AWS ALB client-certificate enrichment is optional
and disabled by default.

## Request lifecycle

One audit event is created when a `/fhir` request finishes, including handled
errors and unhandled failures. Health, readiness, metrics, and discovery
endpoints are not audited.

The middleware retains context obtained before a failure. For example, if PCM
introspection succeeds but a downstream FHIR request fails, the audit event can
still include the PCM scope, consent ID, organization ID, and masked patient
identifier.

Audit delivery is fail-open. A target failure is reported through the
application logger but does not replace or delay the FHIR response with an
audit-specific error.

## Recommended ECS configuration

For a container platform that collects stdout, use:

```text
DS_ADAPTER_AUDIT_ENABLED=true
DS_ADAPTER_AUDIT_FORMAT=ecs
DS_ADAPTER_AUDIT_TARGETS_STDOUT_ENABLED=true
DS_ADAPTER_AUDIT_TARGETS_FILE_ENABLED=false
```

Each line written to stdout is one JSON document. Some Kubernetes logging
agents wrap container output in a string field named `message`. Configure the
collector to decode that JSON string into document fields if fields such as
`event.outcome`, `trace.id`, and `pcm.consent_id` must be independently
searchable.

The `json` and `cef` formats remain available for existing integrations. All
enabled targets receive the same formatted event. Target-specific settings are
listed in `config.yaml` and can be overridden with `DS_ADAPTER_...`
environment variables.

## ECS event fields

Fields are included when their values are available at the point where request
processing ends.

| Field | Meaning |
|---|---|
| `@timestamp` | UTC event timestamp |
| `message` | Stable human-readable audit description |
| `service.name` | OpenTelemetry service name configured for this instance |
| `log.logger`, `log.level` | Audit logger identity and outcome-based severity |
| `event.kind` | ECS event kind (`event`) |
| `event.category`, `event.type` | ECS classification (`web`, `access`) |
| `event.action` | Stable action name (`fhir_access`) |
| `event.dataset` | Stable dataset name (`pcm-connect.audit`) |
| `event.outcome` | `success` or `failure` |
| `event.duration` | Request duration in nanoseconds |
| `labels.correlation_id` | Request correlation ID |
| `trace.id`, `transaction.id` | Active OpenTelemetry trace and server-span IDs |
| `source.ip` | Resolved client IP address |
| `http.request.method` | HTTP request method |
| `http.response.status_code` | HTTP response status, when one was produced |
| `url.path` | Proxied request path; query parameters are not recorded |
| `pcm.patient_id` | Patient identifier with all but the last four characters masked |
| `pcm.scope` | Scope returned by PCM introspection |
| `pcm.sp_organization_id` | Service-provider organization ID returned by PCM |
| `pcm.consent_id` | Consent ID returned by PCM |
| `error.code` | PCM Connect application error code, when present |
| `tls.client.*` | Optional trusted client-certificate metadata |

The certificate fields can include the subject, issuer, serial number,
validity period, and subject common name. They never include a PEM certificate,
certificate chain, or private key.

## Trusted client IP

By default, PCM Connect ignores `X-Forwarded-For` and uses the direct peer
address. If the service is reachable only through controlled proxies, configure
the exact number of trusted hops:

```text
DS_ADAPTER_PROXY_HEADERS_TRUSTED_HOPS=1
```

PCM Connect selects the client address from the right side of the forwarded
chain after removing that number of trusted proxy entries. An incorrect value
can allow a caller-supplied address to be treated as authoritative, so keep the
default of `0` unless the complete proxy path is known and controlled.

## Optional AWS ALB mTLS enrichment

Deployments using AWS Application Load Balancer mTLS verify mode can enrich
audit events and the active server span from ALB-generated headers:

```text
DS_ADAPTER_INBOUND_MTLS_TRUST_AWS_ALB_HEADERS=true
```

This setting is not required for audit logging. Leave it disabled for other
ingress implementations or whenever clients can reach the application without
passing through the trusted ALB. When disabled, certificate fields are simply
absent.

When enabled, the application reads these ALB headers:

- `X-Amzn-Mtls-Clientcert-Subject`
- `X-Amzn-Mtls-Clientcert-Issuer`
- `X-Amzn-Mtls-Clientcert-Serial-Number`
- `X-Amzn-Mtls-Clientcert-Validity`

The backend must be protected from direct access, and upstream components must
remove caller-supplied copies of these headers. PCM Connect deliberately
ignores leaf-certificate and certificate-chain headers.

## Privacy and security

Audit events never include request or response bodies, authorization headers,
access tokens, raw certificates, certificate chains, or private keys. Patient
identifiers are masked while retaining the final four characters for
operational correlation. Operators should still treat audit data as sensitive,
apply least-privilege access, encrypt it in transit and at rest, and define
retention appropriate to their legal and organizational requirements.

The compatibility option `audit.include_response` does not enable response-body
capture.

## Verification

After enabling an audit target, send one successful request and one request
with an invalid or inactive token. Confirm that exactly one audit event appears
for each request, that `event.outcome` and the HTTP status match the response,
and that `trace.id` correlates with the corresponding server trace when tracing
is enabled. Also confirm that no bearer token or unmasked patient identifier is
present in the collected document.
