from __future__ import annotations

import json
import os
import time

import structlog
from fastapi import APIRouter, Depends, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.api.dependencies import get_bearer_token, get_correlation_id
from src.auth.cnf import warn_if_cnf_mismatch
from src.auth.jwks import build_jwks, get_signing_kid, load_signing_key_pem
from src.auth.jwt_service import mint_internal_jwt
from src.auth.metadata import (
    build_oauth_authorization_server,
    build_openid_configuration,
    build_smart_configuration,
)
from src.errors import DSAdapterError
from src.observability import metrics

log = structlog.get_logger()

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/.well-known/jwks.json")
async def jwks(request: Request) -> Response:
    _log_discovery_hit(request, "jwks")
    raw = os.environ.get("DS_ADAPTER_JWT_SIGNING_KEY", "")
    if not raw:
        raise DSAdapterError("missing JWT signing key", code="CFG_001")
    pem = load_signing_key_pem(raw)
    payload = build_jwks(pem, request.app.state.config.jwt.algorithm)
    return Response(
        content=json.dumps(payload),
        media_type="application/jwk-set+json",
    )


def _metadata_disabled() -> Response:
    return Response(status_code=404)


def _log_discovery_hit(request: Request, kind: str) -> None:
    """Visible at INFO so we can confirm IRIS / Apache mod_auth_openidc /
    any verifier is actually fetching us live (and not serving from cache).
    """
    client = request.client.host if request.client else "unknown"
    log.info(
        "discovery_hit",
        kind=kind,
        path=request.url.path,
        source_ip=client,
        user_agent=request.headers.get("user-agent", ""),
        x_forwarded_for=request.headers.get("x-forwarded-for", ""),
    )


@router.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server(request: Request) -> Response:
    _log_discovery_hit(request, "oauth-authorization-server")
    config = request.app.state.config
    if not config.metadata.enabled:
        return _metadata_disabled()
    return Response(
        content=json.dumps(build_oauth_authorization_server(config)),
        media_type="application/json",
    )


@router.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request) -> Response:
    _log_discovery_hit(request, "openid-configuration")
    config = request.app.state.config
    if not config.metadata.enabled:
        return _metadata_disabled()
    return Response(
        content=json.dumps(build_openid_configuration(config)),
        media_type="application/json",
    )


@router.get("/.well-known/smart-configuration")
async def smart_configuration(request: Request) -> Response:
    _log_discovery_hit(request, "smart-configuration")
    config = request.app.state.config
    if not config.metadata.enabled:
        return _metadata_disabled()
    return Response(
        content=json.dumps(build_smart_configuration(config)),
        media_type="application/json",
    )


@router.get("/ready")
async def ready(request: Request) -> Response:
    import asyncio

    import httpx as _httpx
    from fastapi.responses import JSONResponse

    config = request.app.state.config
    targets = {
        "fhir_server": config.fhir_server.base_url,
        "pcm": config.pcm.base_url,
    }

    async def _probe(url: str) -> bool:
        try:
            async with _httpx.AsyncClient(timeout=5.0, verify=False) as probe_client:
                resp = await probe_client.head(url)
                return resp.status_code < 500
        except _httpx.RequestError:
            return False

    results = await asyncio.gather(*(_probe(url) for url in targets.values()))
    statuses = {name: ("ok" if ok else "error") for name, ok in zip(targets.keys(), results)}
    all_ok = all(results)
    payload = {"status": "ready" if all_ok else "not_ready", **statuses}
    return JSONResponse(content=payload, status_code=200 if all_ok else 503)


_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "content-encoding",
}


def _filter_response_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


@router.api_route("/fhir/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def fhir_proxy(
    path: str,
    request: Request,
    bearer_token: str = Depends(get_bearer_token),
    correlation_id: str = Depends(get_correlation_id),
) -> Response:
    state = request.app.state
    config = state.config

    t0 = time.perf_counter()
    introspection = await state.pcm_client.introspect(bearer_token)
    metrics.PCM_INTROSPECT_DURATION.observe(time.perf_counter() - t0)
    warn_if_cnf_mismatch(introspection.cnf, peer_cert_der=None)

    # Persist PCM context immediately so downstream failures still produce a
    # useful audit event.
    request.state.pcm_patient_id = introspection.patient
    request.state.fhir_scope = introspection.scope
    request.state.consent_id = introspection.consent_id
    request.state.sp_organization_id = introspection.sp_organization_id

    if not introspection.patient:
        raise DSAdapterError("introspection missing patient", code="AUTH_002")

    t0 = time.perf_counter()
    local_patient_id = await state.id_replacement_client.resolve_patient_id(
        introspection.patient
    )
    metrics.ID_REPLACEMENT_DURATION.observe(time.perf_counter() - t0)

    signing_key_raw = os.environ.get("DS_ADAPTER_JWT_SIGNING_KEY", "")
    if not signing_key_raw:
        raise DSAdapterError("missing JWT signing key", code="CFG_001")
    signing_key = load_signing_key_pem(signing_key_raw)
    kid = get_signing_kid(signing_key, config.jwt.algorithm)

    # `aud` falls back to the FHIR server base URL if the operator hasn't
    # explicitly configured `jwt.audience`. The FHIR server (e.g. IRIS) MUST
    # accept this exact value as a valid `aud`. If `audience` is a list,
    # the JWT will encode it as a JSON array per RFC 7519.
    audience: str | list[str] = config.jwt.audience or config.fhir_server.base_url

    internal_jwt = mint_internal_jwt(
        issuer=config.jwt.issuer,
        audience=audience,
        patient_id=local_patient_id,
        consent_id=introspection.consent_id,
        scope=introspection.scope,
        baskets=introspection.baskets,
        access_type=introspection.access_type,
        sp_organization_id=introspection.sp_organization_id,
        correlation_id=correlation_id,
        signing_key=signing_key,
        expiry_seconds=config.jwt.expiry_seconds,
        algorithm=config.jwt.algorithm,
        kid=kid,
    )

    _STRIP_INBOUND = _HOP_BY_HOP | {"authorization", "x-correlation-id", "accept-encoding"}
    forward_headers: dict[str, str] = {}
    for k, v in request.headers.items():
        lower_name = k.lower()
        if lower_name in _STRIP_INBOUND or lower_name.startswith("x-amzn-mtls-"):
            continue
        forward_headers[k] = v
    forward_headers["Authorization"] = f"Bearer {internal_jwt}"
    forward_headers["X-Correlation-ID"] = correlation_id

    log.debug(
        "fhir_forward_jwt",
        kid=kid,
        iss=config.jwt.issuer,
        aud=audience,
        alg=config.jwt.algorithm,
        ttl_seconds=config.jwt.expiry_seconds,
        token_preview=internal_jwt[:12] + "..." + internal_jwt[-6:],
    )

    body = await request.body()
    t0 = time.perf_counter()
    fhir_resp = await state.fhir_client.forward(
        method=request.method,
        path=path,
        query_string=request.url.query,
        headers=forward_headers,
        body=body if body else None,
    )
    metrics.FHIR_FORWARD_DURATION.observe(time.perf_counter() - t0)

    request.state.fhir_status = fhir_resp.status_code
    request.state.local_patient_id = local_patient_id

    if state.verifier is not None:
        state.verifier.verify(fhir_resp.body)

    out_headers = _filter_response_headers(fhir_resp.headers)
    out_headers.setdefault("Content-Type", "application/fhir+json")
    return Response(
        content=fhir_resp.body,
        status_code=fhir_resp.status_code,
        headers=out_headers,
    )
