from __future__ import annotations

import logging

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.errors import DSAdapterError
from src.errors.catalog import ERROR_CATALOG
from src.errors.models import build_operation_outcome
from src.observability import metrics

log = structlog.get_logger()


def _response_for_code(request: Request, code: str, *, log_level: int = logging.WARNING) -> JSONResponse:
    request.state.error_code = code
    spec = ERROR_CATALOG.get(code) or ERROR_CATALOG["GEN_001"]
    body = build_operation_outcome(code)
    headers = {}
    correlation_id = getattr(request.state, "correlation_id", None)
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
    log.log(log_level, "request_failed", error_code=code, status=spec["status"], path=request.url.path)
    metrics.ERRORS_TOTAL.labels(error_code=code).inc()
    return JSONResponse(
        content=body,
        status_code=spec["status"],
        headers=headers,
        media_type="application/fhir+json",
    )


async def _ds_adapter_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DSAdapterError)
    return _response_for_code(request, exc.code, log_level=logging.WARNING)


async def _generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception", path=request.url.path, exc_info=exc)
    return _response_for_code(request, "GEN_001", log_level=logging.ERROR)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DSAdapterError, _ds_adapter_error_handler)
    app.add_exception_handler(Exception, _generic_error_handler)
