from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app import app
from core.config import get_settings

# IRIS FHIR server: https://iris.intersystemsisrael.com/csp/healthshare/fhir1/fhir/r4
# Known patients (resource id → national-id):
#   Patient/17  → 123456782
#   Patient/18  → (own national id)
#   Patient/19  → 345678904  (active)
#   Patient/20  → 456789015  (active)
#   Patient/21  → (own national id)
# Duplicates:
#   il-hdp-pat-dup-456789015         shares 456789015 with Patient/20   — both ACTIVE → 409
#   il-hdp-pat-dup-345678904-inactive shares 345678904 with Patient/19   — inactive    → 200

IDENTIFIER_SYSTEM = "http://fhir.health.gov.il/identifier/il-national-id"
API_AUTH = ("resolver_user", "change-me")


def _setup_testserver_config() -> None:
    os.environ["FHIR_RESOLVE_CONFIG"] = "config.testserver.json"
    get_settings.cache_clear()


@pytest.mark.integration
def test_resolve_patient_17() -> None:
    """Patient/17 has identifier value 123456782 — should resolve cleanly."""
    if os.getenv("RUN_FHIR_TESTSERVER_INTEGRATION") != "1":
        pytest.skip("Set RUN_FHIR_TESTSERVER_INTEGRATION=1 to run")
    _setup_testserver_config()

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/resolve",
            auth=API_AUTH,
            json={"identifier": {"system": IDENTIFIER_SYSTEM, "value": "123456782"}},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["resource_reference"] == "Patient/17"
    assert body["patient_id"] == "17"
    get_settings.cache_clear()


@pytest.mark.integration
def test_resolve_patient_20_canonical() -> None:
    """Identifier value 456789015 exists on both Patient/20 and its duplicate.
    The resolver returns the first bundle entry — Patient/20."""
    if os.getenv("RUN_FHIR_TESTSERVER_INTEGRATION") != "1":
        pytest.skip("Set RUN_FHIR_TESTSERVER_INTEGRATION=1 to run")
    _setup_testserver_config()

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/resolve",
            auth=API_AUTH,
            json={"identifier": {"system": IDENTIFIER_SYSTEM, "value": "456789015"}},
        )

    assert resp.status_code == 200
    body = resp.json()
    # IRIS returns Patient/20 first; duplicate is Patient/il-hdp-pat-dup-456789015
    assert body["resource_reference"] == "Patient/20"
    assert body["patient_id"] == "20"
    get_settings.cache_clear()


@pytest.mark.integration
def test_resolve_not_found() -> None:
    """An identifier value that does not exist in IRIS should yield 404."""
    if os.getenv("RUN_FHIR_TESTSERVER_INTEGRATION") != "1":
        pytest.skip("Set RUN_FHIR_TESTSERVER_INTEGRATION=1 to run")
    _setup_testserver_config()

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/resolve",
            auth=API_AUTH,
            json={"identifier": {"system": IDENTIFIER_SYSTEM, "value": "000000000"}},
        )

    assert resp.status_code == 404
    assert resp.json()["error"] == "patient_not_found"
    get_settings.cache_clear()


@pytest.mark.integration
def test_resolve_patient_19_inactive_dup_filtered() -> None:
    """Identifier value 345678904 exists on Patient/19 (active) and il-hdp-pat-dup-345678904-inactive (active=false).
    Only the active patient should be returned — 200, not 409."""
    if os.getenv("RUN_FHIR_TESTSERVER_INTEGRATION") != "1":
        pytest.skip("Set RUN_FHIR_TESTSERVER_INTEGRATION=1 to run")
    _setup_testserver_config()

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/resolve",
            auth=API_AUTH,
            json={"identifier": {"system": IDENTIFIER_SYSTEM, "value": "345678904"}},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["resource_reference"] == "Patient/19"
    assert body["patient_id"] == "19"
    get_settings.cache_clear()
