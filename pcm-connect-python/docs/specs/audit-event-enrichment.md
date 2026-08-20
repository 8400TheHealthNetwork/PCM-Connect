# Audit event enrichment specification

## Purpose

Extend the structured FHIR audit event with stable identity, an explicit
schema version, FHIR request classification, PCM authorization context, and a
terminal processing stage. The event must remain portable across deployment
platforms and audit targets.

## Compatibility

Existing audit targets and formats remain supported. The legacy JSON and CEF
formats gain fields additively. ECS keeps the existing dataset and
classification fields while replacing the fixed `fhir_access` action with a
specific action such as `fhir_search`, `fhir_read`, or `fhir_update`.

The PCM audit schema starts at `1.0.0`. This version describes PCM Connect's
custom audit fields; it is independent of the Elastic Common Schema version.

## Event identity and schema

Every request produces a new UUID in `event.id`. All enabled targets receive
the same ID because the record is formatted once before delivery.

ECS events contain `ecs.version` and `pcm.audit.schema_version`. The first
identifies the Elastic Common Schema contract; the second versions PCM
Connect's custom audit fields. Legacy JSON exposes the latter as
`audit_schema_version`.

## FHIR request classification

PCM Connect derives classification from the HTTP method and URL path only. It
does not inspect or retain a request body.

The first path segment after `/fhir/` is recorded as
`pcm.fhir.resource_type` only when it has the lexical form of a FHIR resource
type. The derived interaction is recorded as `pcm.fhir.interaction`, and
`event.action` is prefixed with `fhir_`.

| Request shape | Interaction |
|---|---|
| `GET /fhir/{Resource}` | `search` |
| `GET /fhir/{Resource}/{id}` | `read` |
| `POST /fhir/{Resource}/_search` | `search` |
| Any path containing a segment beginning with `$` | `operation` |
| A path containing `_history` | `history` |
| `POST /fhir/{Resource}` | `create` |
| `PUT /fhir/{Resource}[/{id}]` | `update` |
| `PATCH /fhir/{Resource}/{id}` | `patch` |
| `DELETE /fhir/{Resource}/{id}` | `delete` |
| Any unrecognized form | `access` |

Resource instance and history-version identifiers in `url.path` are masked
with the same last-four policy as the patient identifier. Resource types and
FHIR control segments such as `_search`, `_history`, and `$everything` remain
visible for operational analysis.

## Authorization decision

Authorization state is independent from the final HTTP result:

- `allowed`: PCM introspection returned active authorization with the patient
  context required for processing;
- `denied`: bearer validation or PCM authorization rejected the request; or
- `indeterminate`: no authoritative authorization decision was reached, for
  example because PCM was unavailable.

ECS records the value as `pcm.authorization.decision` and the authorization
step as `pcm.authorization.stage`. A request authorized by PCM remains
`allowed` if identity resolution, FHIR forwarding, or response verification
later fails.

## Processing stage

`pcm.audit.processing_stage` records the last active lifecycle stage:

1. `bearer_validation`
2. `pcm_introspection`
3. `identity_resolution`
4. `jwt_minting`
5. `fhir_forward`
6. `response_verification`
7. `completed`

## PCM context

When returned by introspection, ECS includes `pcm.access_type` and
`pcm.baskets` alongside the existing scope, consent, organization, and masked
patient fields. These values describe the authorization used for the request;
they are never sourced from caller-controlled headers.

## Privacy and collection

Patient and URL-path instance identifiers remain masked with only their final
four characters visible. Query strings, request and response bodies, bearer
tokens, authorization headers, complete certificates, certificate chains, and
private keys are not emitted.

The application writes one ECS JSON document per stdout line. Container log
runtimes may place that document inside their own `message` envelope. Decoding
that envelope into searchable fields is a collector responsibility and does
not change the application event contract.

## Acceptance criteria

1. Every event has a valid, unique `event.id` and schema version `1.0.0`.
2. Search, read, create, update, patch, delete, history, operation, and fallback
   request shapes are classified without reading the request body.
3. Successful PCM authorization records baskets, access type, `allowed`, and
   the terminal processing stage.
4. Missing, inactive, and expired tokens record `denied` at the correct
   authorization stage.
5. PCM infrastructure or client-authentication failures record
   `indeterminate`, not `denied`.
6. A downstream failure retains the earlier `allowed` decision and PCM context.
7. Existing JSON and CEF consumers continue to receive their established
   fields, with enrichment added without removing or renaming keys.
8. No newly emitted field contains an access token, unmasked patient ID,
   unmasked FHIR instance ID, clinical body, or raw certificate material.
