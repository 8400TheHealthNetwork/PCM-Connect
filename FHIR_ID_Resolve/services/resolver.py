from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from core.config import Settings


class UpstreamUnavailableError(Exception):
    pass


@dataclass
class ResolveResult:
    patient_id: str
    resource_reference: str


def _extract_patient_resource(payload: dict[str, Any]) -> dict[str, Any] | None:
    entries = payload.get("entry")
    if not isinstance(entries, list) or not entries:
        return None

    first = entries[0]
    if not isinstance(first, dict):
        return None

    resource = first.get("resource")
    if not isinstance(resource, dict):
        return None

    if resource.get("resourceType") != "Patient":
        return None

    return resource


def _extract_identifier_value(resource: dict[str, Any], preferred_system: str) -> str | None:
    identifiers = resource.get("identifier")
    if not isinstance(identifiers, list):
        return None

    for item in identifiers:
        if not isinstance(item, dict):
            continue
        if item.get("system") == preferred_system and isinstance(item.get("value"), str):
            return item["value"]

    return None


def _get_patient_id(resource: dict[str, Any], settings: Settings) -> str | None:
    patient_resource_id = resource.get("id")
    if settings.resolver.patient_id_strategy == "resource_id":
        return patient_resource_id if isinstance(patient_resource_id, str) else None

    preferred_system = settings.resolver.patient_id_identifier_system
    if not preferred_system:
        return None

    identifier_value = _extract_identifier_value(resource, preferred_system)
    if identifier_value:
        return identifier_value

    return patient_resource_id if isinstance(patient_resource_id, str) else None


async def resolve_patient(system: str, value: str, settings: Settings) -> ResolveResult | None:
    search_url = f"{settings.fhir.base_url.rstrip('/')}/Patient"
    params = {
        "identifier": f"{system}|{value}",
        "_count": "1",
    }

    try:
        async with httpx.AsyncClient(
            timeout=settings.fhir.timeout_seconds,
            verify=settings.fhir.verify_ssl,
            headers=settings.fhir.default_headers,
        ) as client:
            response = await client.get(search_url, params=params)
    except httpx.HTTPError as exc:
        raise UpstreamUnavailableError(str(exc)) from exc

    if response.status_code >= 500:
        raise UpstreamUnavailableError(f"FHIR server returned {response.status_code}")

    if response.status_code < 200 or response.status_code >= 300:
        raise UpstreamUnavailableError(f"FHIR server returned unexpected status {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise UpstreamUnavailableError("FHIR server returned invalid JSON") from exc

    resource = _extract_patient_resource(payload)
    if resource is None:
        return None

    patient_id = _get_patient_id(resource, settings)
    if not patient_id:
        raise UpstreamUnavailableError("Patient resource missing usable identifier")

    resource_id = resource.get("id") if isinstance(resource.get("id"), str) else patient_id
    return ResolveResult(patient_id=patient_id, resource_reference=f"Patient/{resource_id}")
