from __future__ import annotations

import asyncio
import os

import httpx
import structlog

from src.config.models import IDReplacementConfig
from src.errors import DSAdapterError

log = structlog.get_logger()

NATIONAL_ID_SYSTEM = "http://fhir.health.gov.il/identifier/il-national-id"


class IDReplacementClient:
    def __init__(self, *, http: httpx.AsyncClient, config: IDReplacementConfig) -> None:
        self._http = http
        self._config = config

    @property
    def url(self) -> str:
        return self._config.base_url.rstrip("/") + self._config.endpoint

    async def resolve_patient_id(self, national_id: str) -> str:
        headers = {"Content-Type": "application/json"}
        auth = os.environ.get("DS_ADAPTER_ID_REPLACEMENT_AUTH")
        if auth:
            headers["Authorization"] = auth

        body = {
            "national_id": {
                "system": NATIONAL_ID_SYSTEM,
                "value": national_id,
            }
        }

        last_error: Exception | None = None
        for attempt in range(1, self._config.retries + 1):
            try:
                resp = await self._http.post(
                    self.url,
                    json=body,
                    headers=headers,
                    timeout=self._config.timeout_seconds,
                )
            except httpx.RequestError as exc:
                last_error = exc
                log.warning(
                    "id_replacement_request_error",
                    attempt=attempt,
                    error=str(exc),
                )
                await asyncio.sleep(self._config.retry_backoff_seconds)
                continue

            if resp.status_code == 200:
                data = resp.json()
                patient_id = data.get("patient_id")
                if not patient_id:
                    raise DSAdapterError("id-replacement missing patient_id", code="ID_001")
                return str(patient_id)
            if resp.status_code == 404:
                raise DSAdapterError("patient not found", code="ID_002")
            # 5xx / other transient — retry
            last_error = DSAdapterError(
                f"id-replacement http {resp.status_code}", code="ID_001"
            )
            log.warning(
                "id_replacement_bad_status",
                attempt=attempt,
                status=resp.status_code,
            )
            if attempt < self._config.retries:
                await asyncio.sleep(self._config.retry_backoff_seconds)

        raise DSAdapterError(
            f"id-replacement exhausted retries: {last_error}", code="ID_001"
        )
