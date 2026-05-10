from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import httpx
from fastapi import FastAPI


def _load_pem(value: str) -> str:
    """Accept either a PEM blob or a file path; return the PEM contents."""
    if not value:
        return ""
    if value.lstrip().startswith("-----BEGIN"):
        return value
    return Path(value).read_text(encoding="utf-8")

from src.api.routes import router
from src.auth.mtls import create_mtls_client
from src.auth.pcm_client import PCMClient
from src.config import load_config
from src.errors.handlers import register_exception_handlers
from src.fhir.client import FHIRClient
from src.identity.id_replacement import IDReplacementClient
from src.logging.setup import configure_logging
from src.middleware.audit_middleware import AuditMiddleware
from src.middleware.correlation import CorrelationMiddleware
from src.middleware.timing import TimingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config_path = os.environ.get("DS_ADAPTER_CONFIG_PATH", "config.yaml")
    config = load_config(config_path)
    app.state.config = config
    configure_logging(config.logging.level)

    pcm_http = create_mtls_client(config.pcm)
    id_http = httpx.AsyncClient()
    fhir_http = httpx.AsyncClient()

    app.state.pcm_http = pcm_http
    app.state.id_http = id_http
    app.state.fhir_http = fhir_http

    app.state.pcm_client = PCMClient(
        http=pcm_http,
        base_url=config.pcm.base_url,
        token_endpoint=config.pcm.token_endpoint,
        introspect_endpoint=config.pcm.introspect_endpoint,
        client_id=os.environ.get("DS_ADAPTER_CLIENT_ID", "ds-adapter"),
        client_signing_key=_load_pem(os.environ.get("DS_ADAPTER_PCM_CLIENT_KEY", "")),
        client_assertion_algorithm=config.pcm.client_assertion_algorithm,
        introspect_auth_method=config.pcm.introspect_auth_method,
        token_resource=config.pcm.token_resource,
    )
    app.state.id_replacement_client = IDReplacementClient(
        http=id_http,
        config=config.id_replacement,
    )
    app.state.fhir_client = FHIRClient(http=fhir_http, config=config.fhir_server)

    # Phase 6 — wire verifier when enabled
    from src.fhir.verification import ResponseVerifier

    app.state.verifier = ResponseVerifier(config.verification) if config.verification.enabled else None

    # Phase 7 — wire audit service
    from src.audit.service import AuditService

    app.state.audit_service = AuditService.from_config(config.audit)
    await app.state.audit_service.start()

    # Phase 8 — observability
    from src.observability.setup import init_otel

    init_otel(app, config.otel)

    try:
        yield
    finally:
        await app.state.audit_service.aclose()
        await pcm_http.aclose()
        await id_http.aclose()
        await fhir_http.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="DS Adapter", lifespan=lifespan)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(CorrelationMiddleware)
    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()
