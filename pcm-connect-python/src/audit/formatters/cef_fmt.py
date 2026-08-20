from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.audit.service import AuditRecord


def _escape(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("\\", "\\\\").replace("=", "\\=").replace("|", "\\|")


def format_cef(rec: "AuditRecord") -> str:
    severity = "5" if rec.severity == "critical" else "3"
    header = "|".join(
        [
            "CEF:0",
            "ds-adapter",
            "DSAdapter",
            rec.audit_schema_version,
            rec.error or "fhir_request",
            "FHIR Request",
            severity,
        ]
    )
    extension_pairs = {
        "externalId": rec.event_id,
        "rt": rec.timestamp,
        "src": rec.source_ip,
        "act": f"fhir_{rec.fhir_interaction}",
        "requestMethod": rec.method,
        "request": rec.path,
        "cs1Label": "correlation_id",
        "cs1": rec.correlation_id,
        "cs2Label": "consent_id",
        "cs2": rec.consent_id,
        "cs3Label": "scope",
        "cs3": rec.fhir_scope,
        "cs4Label": "sp_organization_id",
        "cs4": rec.sp_organization_id,
        "cs5Label": "access_type",
        "cs5": rec.access_type,
        "cs6Label": "baskets",
        "cs6": ",".join(rec.baskets),
        "flexString1Label": "authorization_decision",
        "flexString1": rec.authorization_decision,
        "flexString2Label": "authorization_stage",
        "flexString2": rec.authorization_stage,
        "cat": rec.processing_stage,
        "suid": rec.patient_id,
        "outcome": rec.response_status,
    }
    parts = [f"{k}={_escape(v)}" for k, v in extension_pairs.items() if v is not None]
    return f"{header}|{' '.join(parts)}"
