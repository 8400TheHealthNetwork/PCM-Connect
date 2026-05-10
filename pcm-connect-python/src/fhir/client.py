from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from src.config.models import FHIRServerConfig
from src.errors import DSAdapterError

log = structlog.get_logger()


@dataclass
class FHIRResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes


class FHIRClient:
    def __init__(self, *, http: httpx.AsyncClient, config: FHIRServerConfig) -> None:
        self._http = http
        self._config = config

    async def forward(
        self,
        *,
        method: str,
        path: str,
        query_string: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> FHIRResponse:
        url = self._config.base_url.rstrip("/") + "/" + path.lstrip("/")
        if query_string:
            url = f"{url}?{query_string}"

        try:
            resp = await self._http.request(
                method=method,
                url=url,
                content=body,
                headers=headers,
                timeout=self._config.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            log.warning("fhir_timeout", url=url, error=str(exc))
            raise DSAdapterError("fhir timeout", code="FHIR_002") from exc
        except httpx.RequestError as exc:
            log.warning("fhir_request_error", url=url, error=str(exc))
            raise DSAdapterError("fhir unreachable", code="FHIR_001") from exc

        return FHIRResponse(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            body=resp.content,
        )
