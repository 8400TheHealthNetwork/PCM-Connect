# Elastic audit logging specification

## Purpose

PCM Connect must emit one structured audit event for every `/fhir` request.
The event is written as a single-line ECS-compatible JSON document to stdout so
the platform log collector can deliver it to Elastic. The audit event is
correlated with the OpenTelemetry server span for the same request.

## Scope

This feature applies only to proxied FHIR traffic. Health, readiness,
discovery, and metrics endpoints are excluded. Existing file, syslog, Kafka,
JSON, and CEF targets remain supported.

## Event contract

Every JSON audit event contains:

- `service.name`, `log.logger`, and ECS event classification fields;
- `trace.id`, `transaction.id`, and `labels.correlation_id` when available;
- HTTP method, URL path, response status, outcome, and duration in nanoseconds;
- the masked patient identifier, consent ID, PCM scope, and service-provider
  organization ID when processing reached those stages;
- an application error code for handled and unhandled failures; and
- safe inbound mTLS client-certificate identity metadata when trusted AWS ALB
  headers are enabled.

Patient identifiers expose at most their final four characters. Request and
response bodies, authorization headers, access tokens, complete certificates,
certificate chains, and private keys are never emitted.

`source.ip` is resolved from the right side of `X-Forwarded-For` using the
configured number of trusted proxy hops. With zero trusted hops, the header is
ignored and the direct peer address is used. The same resolved value is added
to the server span as `client.address`.

## AWS ALB mTLS metadata

In AWS ALB mTLS verify mode, PCM Connect reads these default headers:

- `X-Amzn-Mtls-Clientcert-Subject`
- `X-Amzn-Mtls-Clientcert-Issuer`
- `X-Amzn-Mtls-Clientcert-Serial-Number`
- `X-Amzn-Mtls-Clientcert-Validity`

The subject CN is parsed from the RFC 2253 distinguished name. The metadata is
mapped to `tls.client.*` and `tls.client.x509.*` fields in the audit event and
on the active OpenTelemetry server span. The leaf-certificate and certificate-
chain headers are deliberately ignored.

Forwarded certificate headers are untrusted input unless
`inbound_mtls.trust_aws_alb_headers` is enabled. Operators must expose the
backend only through the trusted ALB/ingress path and must ensure intermediaries
do not permit clients to bypass or forge the ALB-owned headers. Renamed ALB
headers are not supported by this version.

## Delivery and failure behavior

The stdout target writes exactly one JSON document per line. Audit delivery is
fail-open: target failures are reported through the application logger but do
not interrupt the FHIR response. Multiple enabled targets receive the same
formatted event.

For Kubernetes collection into Elastic, use:

```text
DS_ADAPTER_AUDIT_ENABLED=true
DS_ADAPTER_AUDIT_FORMAT=ecs
DS_ADAPTER_AUDIT_TARGETS_STDOUT_ENABLED=true
DS_ADAPTER_AUDIT_TARGETS_FILE_ENABLED=false
DS_ADAPTER_INBOUND_MTLS_TRUST_AWS_ALB_HEADERS=true
DS_ADAPTER_PROXY_HEADERS_TRUSTED_HOPS=1
```

`audit.include_response` is retained for configuration compatibility but does
not cause response bodies to be captured.

The existing `json` and `cef` event contracts remain unchanged. ECS output is
an explicit `ecs` format so enabling Elastic delivery does not break existing
file, syslog, or Kafka consumers.

## Acceptance criteria

1. A successful FHIR request produces one event with `event.outcome=success`,
   a measured duration, PCM context, and trace correlation.
2. A handled 4xx/5xx response produces `event.outcome=failure` and the correct
   application `error.code`.
3. PCM context obtained before a downstream failure is retained in the event.
4. Trusted ALB certificate subject, CN, issuer, serial number, and validity are
   present on both the server span and audit event.
5. Missing, malformed, or untrusted certificate headers do not add certificate
   metadata and never fail the request.
6. No sensitive body, bearer token, PEM certificate, or private key is emitted.
7. File rotation set to `none` uses a non-rotating file handler.
8. Source IP resolution ignores untrusted caller-supplied `X-Forwarded-For`
   entries and supports AWS IPv4/IPv6 values with optional client ports.
