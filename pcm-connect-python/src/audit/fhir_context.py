from __future__ import annotations

import re
from dataclasses import dataclass

_RESOURCE_TYPE = re.compile(r"^[A-Z][A-Za-z0-9]{0,63}$")


@dataclass(frozen=True)
class FHIRRequestContext:
    resource_type: str | None
    interaction: str
    audit_path: str

    @property
    def event_action(self) -> str:
        return f"fhir_{self.interaction}"


def classify_fhir_request(method: str, path: str) -> FHIRRequestContext:
    """Classify a proxied FHIR request without inspecting its body or query."""

    segments = [segment for segment in path.split("/") if segment]
    if segments and segments[0].lower() == "fhir":
        segments = segments[1:]

    first = segments[0] if segments else ""
    resource_type = first if _RESOURCE_TYPE.fullmatch(first) else None

    if any(segment.startswith("$") for segment in segments):
        interaction = "operation"
    elif "_history" in segments:
        interaction = "history"
    elif "_search" in segments:
        interaction = "search"
    else:
        upper_method = method.upper()
        if upper_method == "GET" and resource_type:
            interaction = "search" if len(segments) == 1 else "read"
        elif upper_method == "POST" and resource_type:
            interaction = "create"
        elif upper_method == "PUT" and resource_type:
            interaction = "update"
        elif upper_method == "PATCH" and resource_type:
            interaction = "patch"
        elif upper_method == "DELETE" and resource_type:
            interaction = "delete"
        else:
            interaction = "access"

    return FHIRRequestContext(
        resource_type=resource_type,
        interaction=interaction,
        audit_path=_mask_instance_identifiers(path),
    )


def _mask_identifier(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


def _mask_instance_identifiers(path: str) -> str:
    """Mask resource and version IDs while preserving FHIR routing context."""

    segments = path.split("/")
    resource_index = next(
        (
            index
            for index, segment in enumerate(segments)
            if _RESOURCE_TYPE.fullmatch(segment)
        ),
        None,
    )
    if resource_index is None:
        return path

    identifier_index = resource_index + 1
    if identifier_index < len(segments):
        identifier = segments[identifier_index]
        if identifier and not identifier.startswith(("_", "$")):
            segments[identifier_index] = _mask_identifier(identifier)

    if "_history" in segments:
        history_index = segments.index("_history")
        version_index = history_index + 1
        if version_index < len(segments) and segments[version_index]:
            segments[version_index] = _mask_identifier(segments[version_index])

    return "/".join(segments)
