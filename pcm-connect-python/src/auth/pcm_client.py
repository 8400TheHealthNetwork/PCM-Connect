from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog
from pydantic import BaseModel, Field

from src.auth.jwt_service import mint_client_assertion
from src.errors import DSAdapterError

log = structlog.get_logger()

CLIENT_ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
DEFAULT_PCM_ACCESS_TOKEN_SCOPE = "system/*.crus"


class IntrospectionResponse(BaseModel):
    active: bool
    patient: str | None = None
    scope: str | None = None
    consent_id: str | None = None
    baskets: list[str] | None = None
    access_type: str | None = None
    sp_organization_id: str | None = None
    cnf: dict[str, Any] | None = None
    exp: int | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class PCMClient:
    def __init__(
        self,
        *,
        http: httpx.AsyncClient,
        base_url: str,
        token_endpoint: str,
        introspect_endpoint: str,
        client_id: str,
        client_signing_key: str,
        client_assertion_algorithm: str = "ES256",
        client_assertion_audience: str | None = None,
        token_scope: str = DEFAULT_PCM_ACCESS_TOKEN_SCOPE,
        introspect_auth_method: str = "bearer",
        token_refresh_buffer_seconds: int = 5,
    ) -> None:
        self._http = http
        self._base = base_url.rstrip("/")
        self._token_endpoint = token_endpoint
        self._introspect_endpoint = introspect_endpoint
        self._client_id = client_id
        self._signing_key = client_signing_key
        self._algorithm = client_assertion_algorithm
        self._client_assertion_audience = client_assertion_audience
        self._token_scope = token_scope
        self._introspect_auth_method = introspect_auth_method
        self._refresh_buffer = token_refresh_buffer_seconds
        self._cached_token: str | None = None
        self._cached_until: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def token_url(self) -> str:
        return self._base + self._token_endpoint

    @property
    def introspect_url(self) -> str:
        return self._base + self._introspect_endpoint

    async def get_token(self) -> str:
        async with self._lock:
            now = time.monotonic()
            if self._cached_token and now < self._cached_until:
                return self._cached_token

            assertion = mint_client_assertion(
                client_id=self._client_id,
                audience=self._client_assertion_audience or self.token_url,
                signing_key=self._signing_key,
                algorithm=self._algorithm,
            )
            form = {
                "grant_type": "client_credentials",
                "client_assertion_type": CLIENT_ASSERTION_TYPE,
                "client_assertion": assertion,
                "scope": self._token_scope,
            }
            body = urlencode(form)
            try:
                resp = await self._http.post(
                    self.token_url,
                    content=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            except httpx.RequestError as exc:
                log.warning("pcm_token_request_error", error=str(exc))
                raise DSAdapterError(str(exc), code="PCM_001") from exc

            if resp.status_code >= 500:
                raise DSAdapterError(f"PCM token error {resp.status_code}", code="PCM_001")
            if resp.status_code >= 400:
                raise DSAdapterError(f"PCM token error {resp.status_code}", code="PCM_002")

            try:
                data = resp.json()
            except ValueError as exc:
                # Some gateways mask upstream authorization failures as HTTP
                # 200 HTML responses. Treat a non-JSON token response as an
                # authentication failure instead of leaking JSONDecodeError as
                # an internal 500.
                log.warning(
                    "pcm_token_invalid_response",
                    status=resp.status_code,
                    content_type=resp.headers.get("content-type"),
                    upstream_error=resp.headers.get("x-amzn-errortype"),
                )
                raise DSAdapterError("PCM token response was not JSON", code="PCM_002") from exc

            if not isinstance(data, dict):
                log.warning(
                    "pcm_token_invalid_response",
                    status=resp.status_code,
                    content_type=resp.headers.get("content-type"),
                )
                raise DSAdapterError("PCM token response was not an object", code="PCM_002")

            access_token = data.get("access_token")
            if not access_token:
                raise DSAdapterError("PCM did not return access_token", code="PCM_002")

            try:
                expires_in = int(data.get("expires_in", 60))
            except (TypeError, ValueError) as exc:
                raise DSAdapterError("PCM returned invalid expires_in", code="PCM_002") from exc

            self._cached_token = access_token
            self._cached_until = now + max(expires_in - self._refresh_buffer, 1)
            return access_token

    async def introspect(self, opaque_token: str) -> IntrospectionResponse:
        # Per PCM API spec, /introspect body is just `{token}`, and auth is
        # mutualTLS OR bearerAuth. mTLS is handled at transport level; the
        # bearer header is added on top when configured.
        body = urlencode({"token": opaque_token})
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self._introspect_auth_method == "bearer":
            adapter_token = await self.get_token()
            headers["Authorization"] = f"Bearer {adapter_token}"

        try:
            resp = await self._http.post(self.introspect_url, content=body, headers=headers)
        except httpx.RequestError as exc:
            log.warning("pcm_introspect_request_error", error=str(exc))
            raise DSAdapterError(str(exc), code="PCM_001") from exc

        # Try to parse the body as an introspection response regardless of
        # status code — some PCMs return non-2xx with a valid {active: bool}
        # payload when the queried token is invalid. Auth failures (rejected
        # client_assertion) produce bodies that do NOT contain `active`.
        try:
            payload = resp.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict) and "active" in payload:
            introspection = IntrospectionResponse.model_validate(payload)
            if not introspection.active:
                if introspection.exp is not None and introspection.exp < int(time.time()):
                    raise DSAdapterError("token expired", code="AUTH_003")
                raise DSAdapterError("token not active", code="AUTH_002")
            return introspection

        log.warning(
            "pcm_introspect_error_response",
            status=resp.status_code,
            body=resp.text[:500],
        )
        if resp.status_code >= 500:
            raise DSAdapterError(f"PCM introspect error {resp.status_code}", code="PCM_001")
        raise DSAdapterError(f"PCM introspect error {resp.status_code}: {resp.text[:200]}", code="PCM_002")
