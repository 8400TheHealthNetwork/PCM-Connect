from __future__ import annotations

import json
from typing import Any, Iterable

import structlog

from src.config.models import VerificationConfig
from src.errors import DSAdapterError

log = structlog.get_logger()


class ResponseVerifier:
    def __init__(self, config: VerificationConfig) -> None:
        self._config = config
        self._forbidden = set(config.forbidden_labels)

    def verify(self, body: bytes | str | None) -> None:
        if not self._config.enabled or not self._forbidden:
            return
        if not body:
            return
        try:
            payload = json.loads(body if isinstance(body, (str, bytes, bytearray)) else "")
        except (ValueError, TypeError):
            # Non-JSON response — let it pass; spec verifies only structured FHIR
            return

        if not isinstance(payload, dict):
            return

        if payload.get("resourceType") == "Bundle":
            for entry in payload.get("entry") or []:
                resource = (entry or {}).get("resource") or {}
                self._check_resource(resource)
        else:
            self._check_resource(payload)

    def _check_resource(self, resource: dict[str, Any]) -> None:
        meta = resource.get("meta") or {}
        for coding in self._iter_security_codings(meta.get("security")):
            system = coding.get("system") or ""
            code = coding.get("code") or ""
            label = f"{system}|{code}"
            if label in self._forbidden:
                log.critical(
                    "forbidden_security_label_detected",
                    resource_type=resource.get("resourceType"),
                )
                raise DSAdapterError("forbidden security label", code="VRF_001")

    @staticmethod
    def _iter_security_codings(security: Any) -> Iterable[dict[str, Any]]:
        if not security:
            return []
        if isinstance(security, list):
            return [c for c in security if isinstance(c, dict)]
        if isinstance(security, dict):
            return [security]
        return []
