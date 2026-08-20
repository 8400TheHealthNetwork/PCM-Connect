from __future__ import annotations

from datetime import datetime, timezone
import time

import structlog
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from src.audit.service import AuditRecord, AuditService
from src.observability.client_certificate import ClientCertificateMetadata, from_aws_alb_headers
from src.observability.client_ip import resolve_client_ip

log = structlog.get_logger()


class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # Only audit FHIR proxy traffic. Health/metrics/ready are non-sensitive.
        if not request.url.path.startswith("/fhir"):
            return await call_next(request)

        started = time.perf_counter()
        client_certificate: ClientCertificateMetadata | None = None
        config = request.app.state.config
        peer_ip = request.client.host if request.client else ""
        source_ip = resolve_client_ip(
            peer_ip=peer_ip,
            x_forwarded_for=request.headers.get("x-forwarded-for"),
            trusted_proxy_hops=config.proxy_headers.trusted_hops,
        )
        active_span = trace.get_current_span()
        if active_span.is_recording() and source_ip:
            active_span.set_attribute("client.address", source_ip)
        if config.inbound_mtls.trust_aws_alb_headers:
            client_certificate = from_aws_alb_headers(request.headers)
            if client_certificate:
                client_certificate.attach_to_span(active_span)

        response = None
        error_code: str | None = None
        try:
            response = await call_next(request)
            return response
        except Exception as exc:  # noqa: BLE001
            error_code = getattr(exc, "code", "GEN_001")
            raise
        finally:
            response_status = getattr(response, "status_code", None) if response else None
            error_code = getattr(request.state, "error_code", None) or error_code
            failed = response_status is None or response_status >= 400
            audit_service: AuditService | None = getattr(request.app.state, "audit_service", None)
            if audit_service is not None:
                span_context = trace.get_current_span().get_span_context()
                trace_id = f"{span_context.trace_id:032x}" if span_context.is_valid else None
                transaction_id = f"{span_context.span_id:016x}" if span_context.is_valid else None
                rec = AuditRecord(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    correlation_id=getattr(request.state, "correlation_id", ""),
                    source_ip=source_ip,
                    method=request.method,
                    path=request.url.path,
                    fhir_scope=getattr(request.state, "fhir_scope", None),
                    patient_id=(
                        getattr(request.state, "local_patient_id", None)
                        or getattr(request.state, "pcm_patient_id", None)
                    ),
                    sp_organization_id=getattr(request.state, "sp_organization_id", None),
                    consent_id=getattr(request.state, "consent_id", None),
                    response_status=response_status,
                    response_time_ms=(time.perf_counter() - started) * 1000.0,
                    service_name=config.otel.service_name,
                    trace_id=trace_id,
                    transaction_id=transaction_id,
                    event_outcome="failure" if failed else "success",
                    client_certificate=client_certificate,
                    error=error_code,
                    severity=(
                        "error"
                        if response_status is None or response_status >= 500
                        else "warning" if failed else "info"
                    ),
                )
                try:
                    await audit_service.record(rec)
                except Exception as exc:  # noqa: BLE001
                    log.warning("audit_emit_failed", error=str(exc))
