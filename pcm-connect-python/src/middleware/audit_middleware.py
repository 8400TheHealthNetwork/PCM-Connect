from __future__ import annotations

from datetime import datetime, timezone

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from src.audit.service import AuditRecord, AuditService

log = structlog.get_logger()


class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # Only audit FHIR proxy traffic. Health/metrics/ready are non-sensitive.
        if not request.url.path.startswith("/fhir"):
            return await call_next(request)

        response = None
        error_code: str | None = None
        try:
            response = await call_next(request)
            return response
        except Exception as exc:  # noqa: BLE001
            error_code = getattr(exc, "code", "GEN_001")
            raise
        finally:
            audit_service: AuditService | None = getattr(request.app.state, "audit_service", None)
            if audit_service is not None:
                rec = AuditRecord(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    correlation_id=getattr(request.state, "correlation_id", ""),
                    source_ip=request.client.host if request.client else "",
                    method=request.method,
                    path=request.url.path,
                    fhir_scope=getattr(request.state, "fhir_scope", None),
                    patient_id=getattr(request.state, "local_patient_id", None),
                    sp_organization_id=getattr(request.state, "sp_organization_id", None),
                    consent_id=getattr(request.state, "consent_id", None),
                    response_status=getattr(response, "status_code", None) if response else None,
                    response_time_ms=getattr(request.state, "response_time_ms", None),
                    error=error_code,
                )
                try:
                    await audit_service.record(rec)
                except Exception as exc:  # noqa: BLE001
                    log.warning("audit_emit_failed", error=str(exc))
