from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.audit.service import AuditRecord

ECS_VERSION = "8.0.0"


def format_ecs(rec: "AuditRecord") -> str:
    event: dict[str, object] = {
        "id": rec.event_id,
        "kind": "event",
        "category": ["web"],
        "type": ["access"],
        "action": f"fhir_{rec.fhir_interaction}",
        "dataset": "pcm-connect.audit",
        "outcome": rec.event_outcome,
    }
    if rec.response_time_ms is not None:
        event["duration"] = int(rec.response_time_ms * 1_000_000)

    body: dict[str, object] = {
        "@timestamp": rec.timestamp,
        "message": "FHIR access audit",
        "ecs": {"version": ECS_VERSION},
        "service": {"name": rec.service_name},
        "log": {"logger": "audit", "level": rec.severity},
        "event": event,
        "labels": {"correlation_id": rec.correlation_id},
        "source": {"ip": rec.source_ip},
        "http": {
            "request": {"method": rec.method},
            "response": {"status_code": rec.response_status},
        },
        "url": {"path": rec.path},
        "pcm": {
            "audit": {
                "schema_version": rec.audit_schema_version,
                "processing_stage": rec.processing_stage,
            },
            "fhir": {
                "resource_type": rec.fhir_resource_type,
                "interaction": rec.fhir_interaction,
            },
            "authorization": {
                "decision": rec.authorization_decision,
                "stage": rec.authorization_stage,
            },
            "patient_id": rec.patient_id,
            "scope": rec.fhir_scope,
            "baskets": list(rec.baskets),
            "access_type": rec.access_type,
            "sp_organization_id": rec.sp_organization_id,
            "consent_id": rec.consent_id,
        },
    }
    if rec.trace_id:
        body["trace"] = {"id": rec.trace_id}
    if rec.transaction_id:
        body["transaction"] = {"id": rec.transaction_id}
    if rec.error:
        body["error"] = {"code": rec.error}
    if rec.client_certificate:
        cert = rec.client_certificate
        client: dict[str, object] = {
            "subject": cert.subject,
            "issuer": cert.issuer,
            "not_before": cert.not_before,
            "not_after": cert.not_after,
            "x509": {
                "serial_number": cert.serial_number,
                "subject": {
                    "distinguished_name": cert.subject,
                    "common_name": list(cert.common_names),
                },
                "issuer": {"distinguished_name": cert.issuer},
            },
        }
        body["tls"] = {"established": True, "client": client}
    if rec.extras:
        body["custom"] = rec.extras
    return json.dumps(body, ensure_ascii=False)
