from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from src.observability import metrics


def _path_label(path: str) -> str:
    # Collapse anything under /fhir to keep cardinality bounded.
    if path.startswith("/fhir"):
        return "/fhir"
    return path


class TimingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        start = time.perf_counter()
        request.state.start_time = start
        path_label = _path_label(request.url.path)
        try:
            response = await call_next(request)
        finally:
            elapsed = time.perf_counter() - start
            request.state.response_time_ms = elapsed * 1000.0
            metrics.REQUEST_DURATION.labels(method=request.method, path=path_label).observe(elapsed)

        metrics.REQUESTS_TOTAL.labels(
            method=request.method,
            status=str(response.status_code),
            path=path_label,
        ).inc()
        response.headers["X-Response-Time-Ms"] = f"{request.state.response_time_ms:.2f}"
        return response
