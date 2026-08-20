# Collecting PCM audit events with Elastic

This guide describes one portable way to collect PCM Connect ECS audit events
from Kubernetes container stdout with Elastic Agent. It complements the
[audit logging guide](audit.md); it does not change the application event
contract and is not required when another collector already decodes JSON
stdout.

The examples use the Elastic Kubernetes container-log dataset. Replace values
inside angle brackets with deployment-specific values and adapt the pipeline
name if the logs use a different dataset.

## Application configuration

Emit one ECS JSON document per stdout line:

```text
DS_ADAPTER_AUDIT_ENABLED=true
DS_ADAPTER_AUDIT_FORMAT=ecs
DS_ADAPTER_AUDIT_TARGETS_STDOUT_ENABLED=true
DS_ADAPTER_AUDIT_TARGETS_FILE_ENABLED=false
```

The container runtime and Elastic Agent normally place that JSON document in
the collected document's string-valued `message` field. The ingest pipeline
below promotes the audit fields to the root while preserving collector fields
such as `kubernetes.*` and `log.file.path`.

## Use the Fleet custom-pipeline hook

For the `kubernetes.container_logs` dataset, Fleet supports the custom ingest
pipeline named:

```text
logs-kubernetes.container_logs@custom
```

Create it if it does not exist. If it already exists, export a backup and
append the PCM processors to its existing `processors` array. Do not replace
processors owned by other applications.

Use a narrow condition so ordinary application and sidecar logs are not parsed
as audit events. For example:

```painless
ctx?.kubernetes?.namespace == '<namespace>' &&
ctx?.kubernetes?.container?.name == '<container-name>' &&
ctx.message != null &&
ctx.message.startsWith('{') &&
ctx.message.contains('"pcm-connect.audit"')
```

Append these processors in order, using that condition for the first two:

```json
{
  "set": {
    "description": "Preserve the original PCM audit document",
    "if": "<pre-parse-condition>",
    "field": "event.original",
    "copy_from": "message",
    "override": false,
    "ignore_empty_value": true,
    "tag": "pcm_audit_preserve_original"
  }
}
```

```json
{
  "json": {
    "description": "Decode PCM audit ECS JSON into root fields",
    "if": "<pre-parse-condition>",
    "field": "message",
    "add_to_root": true,
    "add_to_root_conflict_strategy": "merge",
    "tag": "pcm_audit_decode_ecs",
    "on_failure": [
      {
        "append": {
          "field": "tags",
          "value": "pcm_audit_json_parse_failure",
          "allow_duplicates": false
        }
      }
    ]
  }
}
```

Use this post-parse condition after the JSON processor:

```painless
ctx?.kubernetes?.namespace == '<namespace>' &&
ctx?.kubernetes?.container?.name == '<container-name>' &&
ctx?.pcm?.audit?.schema_version != null &&
ctx?.log?.logger == 'audit' &&
ctx?.event?.id != null
```

Finally, append this processor with that condition. The
`preserve_original_event` tag prevents the outer Fleet pipeline from removing
`event.original`:

```json
{
  "append": {
    "description": "Keep the original PCM audit JSON through Fleet processing",
    "if": "<post-parse-condition>",
    "field": "tags",
    "value": "preserve_original_event",
    "allow_duplicates": false,
    "tag": "pcm_audit_keep_original_tag"
  }
}
```

Keep `add_to_root_conflict_strategy` set to `merge`. Replacing root objects can
discard collector metadata nested under fields also emitted by the application,
such as `log.file.path`.

## Map PCM fields

Add explicit mappings for frequently filtered PCM fields to the custom
component template for the dataset. For the Kubernetes container-log dataset,
the component template is normally:

```text
logs-kubernetes.container_logs@custom
```

Merge the following `pcm` property into the existing
`template.mappings.properties` object:

```json
{
  "pcm": {
    "properties": {
      "audit": {
        "properties": {
          "schema_version": { "type": "keyword" },
          "processing_stage": { "type": "keyword" }
        }
      },
      "fhir": {
        "properties": {
          "resource_type": { "type": "keyword" },
          "interaction": { "type": "keyword" }
        }
      },
      "authorization": {
        "properties": {
          "decision": { "type": "keyword" },
          "stage": { "type": "keyword" }
        }
      },
      "patient_id": { "type": "keyword" },
      "scope": { "type": "keyword", "ignore_above": 2048 },
      "baskets": { "type": "keyword" },
      "access_type": { "type": "keyword" },
      "sp_organization_id": { "type": "keyword" },
      "consent_id": { "type": "keyword" }
    }
  }
}
```

Retrieve and back up the current component template before updating it. Merge
the mapping into its full definition; sending only this fragment would remove
unrelated settings and mappings from a shared template.

Component-template mapping changes apply to new backing indices. After
verifying the merged template, roll over the data stream once:

```http
POST logs-kubernetes.container_logs-<data-stream-namespace>/_rollover
```

Pipeline changes apply only to newly ingested events. Existing documents stay
in their original form unless an operator deliberately reindexes them.

## Verify before and after rollout

Before updating a live pipeline, use the ingest pipeline simulate API with:

1. a representative PCM audit JSON line;
2. an ordinary application log from the same container; and
3. a log from another container using the shared dataset.

Confirm that the audit document gains root `event.*`, `pcm.*`, `trace.id`, and
`event.original` fields; collector fields remain present; and both non-audit
documents remain unchanged. Back up both the pipeline and component template
before mutation and verify their complete definitions after mutation.

Then send one successful FHIR request and one request with an inactive token.
Each request must create exactly one structured audit event. The ordinary
application error log may still be present as a separate, unparsed log event;
it is not an audit duplicate.

Some managed Kubernetes pipelines set the root `event.dataset` back to
`kubernetes.container_logs` after the custom hook. This is expected because the
document remains in that data stream. Select PCM audits using
`pcm.audit.schema_version` and `log.logger`, rather than relying on the root
`event.dataset`. The application's original `pcm-connect.audit` value remains
inside `event.original`.

### KQL in Discover classic mode

Select a data view covering `logs-kubernetes.container_logs-*`, then use:

```kql
log.logger:"audit" and pcm.audit.schema_version:*
```

To locate one request, add its correlation ID:

```kql
log.logger:"audit" and pcm.audit.schema_version:* and labels.correlation_id:"<correlation-id>"
```

### ES|QL in Discover

```esql
FROM logs-kubernetes.container_logs-*
| WHERE log.logger == "audit" AND pcm.audit.schema_version IS NOT NULL
| SORT @timestamp DESC
| KEEP @timestamp,
       event.id,
       event.action,
       event.outcome,
       labels.correlation_id,
       pcm.audit.processing_stage,
       pcm.fhir.resource_type,
       pcm.fhir.interaction,
       pcm.authorization.decision,
       pcm.authorization.stage,
       pcm.patient_id,
       source.ip,
       tls.client.x509.subject.common_name,
       trace.id,
       transaction.id,
       http.request.method,
       http.response.status_code,
       url.path
| LIMIT 100
```

## Operational safeguards

- Treat `event.original` and all audit fields as sensitive operational data.
- Apply least-privilege read access, encryption, and an approved retention
  policy.
- Alert on `pcm_audit_json_parse_failure`; it indicates schema drift or a
  collector condition that is too broad.
- Keep namespace and container checks in the pre-parse condition when a data
  stream is shared.
- Re-run the simulation and live verification after Elastic integration
  upgrades because managed pipeline ordering can change.
