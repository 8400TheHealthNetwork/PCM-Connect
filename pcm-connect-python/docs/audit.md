# Audit logging

PCM Connect emits one security audit event for every request handled by the
`/fhir` proxy. Audit events are separate from application logs and
OpenTelemetry traces, but ECS events include identifiers that correlate all
three signals.

The implementation is platform-neutral. Events can be sent to stdout, a file,
syslog, or Kafka. ECS output is suitable for Elastic and other collectors that
accept structured JSON. AWS ALB client-certificate enrichment is optional and
disabled by default.

## Request lifecycle

An event is created when a `/fhir` request finishes, including handled errors
and unhandled failures. Health, readiness, metrics, and discovery endpoints are
not audited. The event retains context obtained before a failure.

`event.outcome` describes whether request processing succeeded. Authorization
is recorded independently in `pcm.authorization.decision`:

- `allowed`: PCM authorized the request, even if a downstream step later
  failed;
- `denied`: bearer validation or PCM authorization rejected the request; or
- `indeterminate`: an authoritative decision was not reached, such as when PCM
  was unavailable or rejected the adapter's own credentials.

`pcm.audit.processing_stage` identifies where processing ended. Its values are
`bearer_validation`, `pcm_introspection`, `identity_resolution`, `jwt_minting`,
`fhir_forward`, `response_verification`, and `completed`.

Audit delivery is fail-open. A target failure is reported through the
application logger but does not replace the FHIR response with an audit error.

## Recommended ECS configuration

For a container platform that collects stdout, use:

```text
DS_ADAPTER_AUDIT_ENABLED=true
DS_ADAPTER_AUDIT_FORMAT=ecs
DS_ADAPTER_AUDIT_TARGETS_STDOUT_ENABLED=true
DS_ADAPTER_AUDIT_TARGETS_FILE_ENABLED=false
```

Each stdout line is one JSON document. Some Kubernetes logging agents wrap
container output in a string field named `message`. Configure the collector to
decode that JSON string into document fields when fields such as `event.id`,
`event.outcome`, `trace.id`, and `pcm.authorization.decision` must be directly
searchable. This collector step is independent of PCM Connect. Elastic Agent
operators can use the merge-safe pipeline, mapping, rollover, and verification
procedure in [Collecting PCM audit events with Elastic](elastic-audit-ingest.md).

The `json` and `cef` formats remain available for existing integrations. All
enabled targets receive the same formatted event. Target settings are listed
in `config.yaml` and can be overridden with `DS_ADAPTER_...` environment
variables.

## ECS event fields

Context values that have not been obtained when processing ends are represented
as `null` or an empty list. Trace, error, and certificate objects are omitted
when they are unavailable.

| Field | Meaning |
|---|---|
| `@timestamp` | UTC event timestamp |
| `message` | Stable human-readable audit description |
| `ecs.version` | ECS contract used by the event (`8.0.0`) |
| `service.name` | OpenTelemetry service name configured for this instance |
| `log.logger`, `log.level` | Audit logger identity and outcome-based severity |
| `event.id` | Unique UUID for this audit event |
| `event.kind` | ECS event kind (`event`) |
| `event.category`, `event.type` | ECS classification (`web`, `access`) |
| `event.action` | Derived action such as `fhir_search`, `fhir_read`, or `fhir_update` |
| `event.dataset` | Stable dataset name (`pcm-connect.audit`) |
| `event.outcome` | Technical request result: `success` or `failure` |
| `event.duration` | Request duration in nanoseconds |
| `labels.correlation_id` | Request correlation ID |
| `trace.id`, `transaction.id` | Active OpenTelemetry trace and server-span IDs |
| `source.ip` | Resolved client IP address |
| `http.request.method` | HTTP request method |
| `http.response.status_code` | HTTP response status, when one was produced |
| `url.path` | Proxied request path with resource/version IDs masked; query parameters are not recorded |
| `pcm.audit.schema_version` | PCM Connect custom audit contract version |
| `pcm.audit.processing_stage` | Last active request-processing stage |
| `pcm.fhir.resource_type` | Resource type derived from the first FHIR path segment |
| `pcm.fhir.interaction` | Derived FHIR interaction, such as `search`, `read`, or `create` |
| `pcm.authorization.decision` | `allowed`, `denied`, or `indeterminate` |
| `pcm.authorization.stage` | Authorization step at which the decision was recorded |
| `pcm.patient_id` | Patient identifier with all but the final four characters masked |
| `pcm.scope` | Scope returned by PCM introspection |
| `pcm.baskets` | Authorization baskets returned by PCM introspection |
| `pcm.access_type` | Access type returned by PCM introspection |
| `pcm.sp_organization_id` | Service-provider organization ID returned by PCM |
| `pcm.consent_id` | Consent ID returned by PCM |
| `error.code` | PCM Connect application error code, when present |
| `tls.client.*` | Optional trusted client-certificate metadata |

FHIR interaction classification uses only the method and path. Request and
response bodies are not parsed for audit purposes. Operations containing a
`$` path segment, `_history` requests, and POST `_search` requests are
classified explicitly; unknown forms retain the fallback `fhir_access` action.
FHIR instance and history-version identifiers in the path retain only their
final four characters.

Certificate fields can include the subject, issuer, serial number, validity
period, and subject common name. They never include a PEM certificate,
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

This is not required for audit logging. Leave it disabled for other ingress
implementations or whenever clients can reach the application without passing
through the trusted ALB. When disabled, certificate fields are absent.

When enabled, the application reads these ALB headers:

- `X-Amzn-Mtls-Clientcert-Subject`
- `X-Amzn-Mtls-Clientcert-Issuer`
- `X-Amzn-Mtls-Clientcert-Serial-Number`
- `X-Amzn-Mtls-Clientcert-Validity`

The backend must be protected from direct access, and upstream components must
remove caller-supplied copies of these headers. PCM Connect deliberately
ignores leaf-certificate and certificate-chain headers.

## Privacy and security

Audit events never include query strings, request or response bodies,
authorization headers, access tokens, raw certificates, certificate chains,
or private keys. Patient identifiers and identifier-like FHIR path segments are
masked while retaining the final four characters for operational correlation.

Operators should still treat audit data as sensitive, apply least-privilege
access, encrypt it in transit and at rest, and define retention appropriate to
their legal and organizational requirements. The compatibility option
`audit.include_response` does not enable response-body capture.

## Verification

After enabling a target, send a successful request, a request with an inactive
token, and—where practical—a request that fails after PCM authorization.
Confirm that:

1. exactly one audit event appears for each request;
2. each event has a different `event.id`;
3. `event.outcome`, the HTTP status, and `pcm.audit.processing_stage` match the
   request result;
4. authorization is `denied` for the inactive token but remains `allowed` for
   the downstream failure;
5. PCM baskets and access type appear only after successful introspection;
6. `trace.id` correlates with the server trace when tracing is enabled; and
7. no bearer token, clinical body, raw certificate, or unmasked patient ID is
   present.
