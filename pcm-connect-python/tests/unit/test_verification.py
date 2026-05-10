from __future__ import annotations

import json

import pytest

from src.config.models import VerificationConfig
from src.errors import DSAdapterError
from src.fhir.verification import ResponseVerifier

FORBIDDEN = "http://fhir.health.gov.il/cs/il-core-main-security-label|V"


def _verifier(*, enabled: bool = True, labels: list[str] | None = None) -> ResponseVerifier:
    return ResponseVerifier(
        VerificationConfig(enabled=enabled, forbidden_labels=labels or [FORBIDDEN])
    )


def test_bundle_without_labels_passes() -> None:
    body = json.dumps(
        {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Observation"}}]}
    )
    _verifier().verify(body)


def test_bundle_with_v_label_fails() -> None:
    body = json.dumps(
        {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Observation",
                        "meta": {
                            "security": [
                                {
                                    "system": "http://fhir.health.gov.il/cs/il-core-main-security-label",
                                    "code": "V",
                                }
                            ]
                        },
                    }
                }
            ],
        }
    )
    with pytest.raises(DSAdapterError) as exc_info:
        _verifier().verify(body)
    assert exc_info.value.code == "VRF_001"


def test_single_resource_with_v_label_fails() -> None:
    body = json.dumps(
        {
            "resourceType": "Observation",
            "meta": {
                "security": [
                    {
                        "system": "http://fhir.health.gov.il/cs/il-core-main-security-label",
                        "code": "V",
                    }
                ]
            },
        }
    )
    with pytest.raises(DSAdapterError) as exc_info:
        _verifier().verify(body)
    assert exc_info.value.code == "VRF_001"


def test_disabled_skips() -> None:
    body = json.dumps(
        {
            "resourceType": "Observation",
            "meta": {
                "security": [
                    {
                        "system": "http://fhir.health.gov.il/cs/il-core-main-security-label",
                        "code": "V",
                    }
                ]
            },
        }
    )
    _verifier(enabled=False).verify(body)


def test_empty_bundle_passes() -> None:
    _verifier().verify(json.dumps({"resourceType": "Bundle", "entry": []}))


def test_non_json_body_passes_silently() -> None:
    _verifier().verify(b"not json at all")


def test_bytes_body_supported() -> None:
    body = json.dumps({"resourceType": "Observation"}).encode()
    _verifier().verify(body)
