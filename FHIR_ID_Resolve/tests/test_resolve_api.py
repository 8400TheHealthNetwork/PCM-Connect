from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import app
from core.config import get_settings
from services.resolver import ResolveResult, UpstreamUnavailableError


TEST_USERNAME = "test_user"
TEST_PASSWORD = "test_pass"


def _write_test_config(path: Path) -> None:
    payload = {
        "api": {"host": "127.0.0.1", "port": 8010},
        "auth": {"username": TEST_USERNAME, "password": TEST_PASSWORD},
        "fhir": {
            "base_url": "http://example-fhir.local/fhir/r4",
            "timeout_seconds": 5.0,
            "verify_ssl": True,
            "default_headers": {},
        },
        "resolver": {
            "patient_id_strategy": "resource_id",
            "patient_id_identifier_system": None,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _auth() -> tuple[str, str]:
    return TEST_USERNAME, TEST_PASSWORD


def test_resolve_returns_200_when_patient_found(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "test_config.json"
    _write_test_config(config_path)
    monkeypatch.setenv("FHIR_RESOLVE_CONFIG", str(config_path))
    get_settings.cache_clear()

    async def fake_resolve_patient(system: str, value: str, settings):
        assert system == "http://fhir.health.gov.il/identifier/il-national-id"
        assert value == "000000018"
        return ResolveResult(patient_id="12345", resource_reference="Patient/12345")

    from api import routes

    monkeypatch.setattr(routes, "resolve_patient", fake_resolve_patient)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/resolve",
            auth=_auth(),
            json={
                "identifier": {
                    "system": "http://fhir.health.gov.il/identifier/il-national-id",
                    "value": "000000018",
                }
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "patient_id": "12345",
        "resource_reference": "Patient/12345",
    }


def test_resolve_returns_404_when_patient_missing(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "test_config.json"
    _write_test_config(config_path)
    monkeypatch.setenv("FHIR_RESOLVE_CONFIG", str(config_path))
    get_settings.cache_clear()

    async def fake_resolve_patient(system: str, value: str, settings):
        return None

    from api import routes

    monkeypatch.setattr(routes, "resolve_patient", fake_resolve_patient)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/resolve",
            auth=_auth(),
            json={
                "identifier": {
                    "system": "http://fhir.health.gov.il/identifier/il-national-id",
                    "value": "000000019",
                }
            },
        )

    assert response.status_code == 404
    assert response.json() == {
        "error": "patient_not_found",
        "message": "No patient was found for the provided identifier",
    }


def test_resolve_returns_401_on_bad_auth(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "test_config.json"
    _write_test_config(config_path)
    monkeypatch.setenv("FHIR_RESOLVE_CONFIG", str(config_path))
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/resolve",
            auth=("wrong_user", "wrong_pass"),
            json={
                "identifier": {
                    "system": "http://fhir.health.gov.il/identifier/il-national-id",
                    "value": "000000018",
                }
            },
        )

    assert response.status_code == 401


def test_resolve_returns_503_when_upstream_unavailable(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "test_config.json"
    _write_test_config(config_path)
    monkeypatch.setenv("FHIR_RESOLVE_CONFIG", str(config_path))
    get_settings.cache_clear()

    async def fake_resolve_patient(system: str, value: str, settings):
        raise UpstreamUnavailableError("timeout")

    from api import routes

    monkeypatch.setattr(routes, "resolve_patient", fake_resolve_patient)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/resolve",
            auth=_auth(),
            json={
                "identifier": {
                    "system": "http://fhir.health.gov.il/identifier/il-national-id",
                    "value": "000000018",
                }
            },
        )

    assert response.status_code == 503
    assert response.json()["error"] == "service_unavailable"


# Keep config cache isolated between tests.
def teardown_function() -> None:
    get_settings.cache_clear()
