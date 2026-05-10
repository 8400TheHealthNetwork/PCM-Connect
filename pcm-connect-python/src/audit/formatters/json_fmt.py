from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.audit.service import AuditRecord


def format_json(rec: "AuditRecord") -> str:
    body = {
        "timestamp": rec.timestamp,
        "correlation_id": rec.correlation_id,
        "source_ip": rec.source_ip,
        "method": rec.method,
        "path": rec.path,
        "fhir_scope": rec.fhir_scope,
        "patient_id": rec.patient_id,
        "sp_organization_id": rec.sp_organization_id,
        "consent_id": rec.consent_id,
        "response_status": rec.response_status,
        "response_time_ms": rec.response_time_ms,
        "error": rec.error,
        "severity": rec.severity,
    }
    if rec.extras:
        body.update(rec.extras)
    return json.dumps(body, ensure_ascii=False)
