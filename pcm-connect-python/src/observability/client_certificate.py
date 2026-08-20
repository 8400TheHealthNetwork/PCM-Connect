from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from cryptography import x509
from cryptography.x509.oid import NameOID
from opentelemetry.trace import Span

_SUBJECT_HEADER = "x-amzn-mtls-clientcert-subject"
_ISSUER_HEADER = "x-amzn-mtls-clientcert-issuer"
_SERIAL_HEADER = "x-amzn-mtls-clientcert-serial-number"
_VALIDITY_HEADER = "x-amzn-mtls-clientcert-validity"
_VALIDITY_PATTERN = re.compile(r"^NotBefore=([^;]+);NotAfter=([^;]+)$")
_SERIAL_PATTERN = re.compile(r"^[0-9A-Fa-f:]+$")
_MAX_DN_LENGTH = 4096
_MAX_VALUE_LENGTH = 256


@dataclass(frozen=True)
class ClientCertificateMetadata:
    subject: str | None = None
    issuer: str | None = None
    serial_number: str | None = None
    not_before: str | None = None
    not_after: str | None = None
    common_names: tuple[str, ...] = ()

    def span_attributes(self) -> dict[str, str | bool | tuple[str, ...]]:
        attributes: dict[str, str | bool | tuple[str, ...]] = {"tls.established": True}
        if self.subject:
            attributes["tls.client.subject"] = self.subject
            attributes["tls.client.x509.subject.distinguished_name"] = self.subject
        if self.issuer:
            attributes["tls.client.issuer"] = self.issuer
            attributes["tls.client.x509.issuer.distinguished_name"] = self.issuer
        if self.serial_number:
            attributes["tls.client.x509.serial_number"] = self.serial_number
        if self.not_before:
            attributes["tls.client.not_before"] = self.not_before
        if self.not_after:
            attributes["tls.client.not_after"] = self.not_after
        if self.common_names:
            attributes["tls.client.x509.subject.common_name"] = self.common_names
        return attributes

    def attach_to_span(self, span: Span) -> None:
        if not span.is_recording():
            return
        for key, value in self.span_attributes().items():
            span.set_attribute(key, value)


def _bounded(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or len(stripped) > limit:
        return None
    return stripped


def _common_names(subject: str | None) -> tuple[str, ...]:
    if subject is None:
        return ()
    try:
        name = x509.Name.from_rfc4514_string(subject)
    except ValueError:
        return ()
    return tuple(attribute.value for attribute in name.get_attributes_for_oid(NameOID.COMMON_NAME))


def _valid_timestamp(value: str) -> str | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.tzinfo is not None else None


def from_aws_alb_headers(headers: Mapping[str, str]) -> ClientCertificateMetadata | None:
    """Build safe metadata from AWS ALB mTLS verify-mode headers.

    The URL-encoded leaf certificate and certificate-chain headers are never
    read, decoded, or retained.
    """

    normalized = {key.lower(): value for key, value in headers.items()}
    subject = _bounded(normalized.get(_SUBJECT_HEADER), _MAX_DN_LENGTH)
    issuer = _bounded(normalized.get(_ISSUER_HEADER), _MAX_DN_LENGTH)

    serial = _bounded(normalized.get(_SERIAL_HEADER), _MAX_VALUE_LENGTH)
    if serial and _SERIAL_PATTERN.fullmatch(serial):
        serial = serial.replace(":", "").upper()
        if not serial:
            serial = None
    else:
        serial = None

    not_before: str | None = None
    not_after: str | None = None
    validity = _bounded(normalized.get(_VALIDITY_HEADER), _MAX_VALUE_LENGTH)
    if validity:
        match = _VALIDITY_PATTERN.fullmatch(validity)
        if match:
            raw_not_before, raw_not_after = match.groups()
            not_before = _valid_timestamp(raw_not_before)
            not_after = _valid_timestamp(raw_not_after)

    if not any((subject, issuer, serial, not_before, not_after)):
        return None
    return ClientCertificateMetadata(
        subject=subject,
        issuer=issuer,
        serial_number=serial,
        not_before=not_before,
        not_after=not_after,
        common_names=_common_names(subject),
    )
