from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app import app
from core.config import get_settings


@pytest.mark.integration
def test_resolve_against_fhir_testserver() -> None:
    if os.getenv("RUN_FHIR_TESTSERVER_INTEGRATION") != "1":
        pytest.skip("Set RUN_FHIR_TESTSERVER_INTEGRATION=1 to run this integration test")

    os.environ["FHIR_RESOLVE_CONFIG"] = "config.testserver.json"
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/resolve",
            auth=("resolver_user", "change-me"),
            json={
                "national_id": {
                    "system": "http://fhir.health.gov.il/identifier/il-national-id",
                    "value": "000000019",
                }
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "patient_id" in body
        assert body["resource_reference"].startswith("Patient/")

        not_found_response = client.post(
            "/api/v1/resolve",
            auth=("resolver_user", "change-me"),
            json={
                "national_id": {
                    "system": "http://fhir.health.gov.il/identifier/il-national-id",
                    "value": "009999999",
                }
            },
        )

        assert not_found_response.status_code == 404
        assert not_found_response.json()["error"] == "patient_not_found"

    get_settings.cache_clear()
