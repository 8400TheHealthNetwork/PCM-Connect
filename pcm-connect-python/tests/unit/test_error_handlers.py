from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.errors import DSAdapterError
from src.errors.catalog import ERROR_CATALOG, ERROR_SYSTEM
from src.errors.handlers import register_exception_handlers
from src.errors.models import build_operation_outcome
from src.middleware.correlation import CorrelationMiddleware


@pytest.mark.parametrize("code", list(ERROR_CATALOG.keys()))
def test_build_operation_outcome_shape(code: str) -> None:
    oo = build_operation_outcome(code)
    spec = ERROR_CATALOG[code]

    assert oo["resourceType"] == "OperationOutcome"
    assert len(oo["issue"]) == 1
    issue = oo["issue"][0]
    assert issue["severity"] == "error"
    assert issue["code"] == spec["issue_code"]
    assert issue["diagnostics"] == spec["diagnostics"]
    coding = issue["details"]["coding"][0]
    assert coding["system"] == ERROR_SYSTEM
    assert coding["code"] == code
    assert coding["display"] == spec["display"]


def test_unknown_code_falls_back_to_gen_001() -> None:
    oo = build_operation_outcome("DOES_NOT_EXIST")
    coding = oo["issue"][0]["details"]["coding"][0]
    assert coding["code"] == "GEN_001"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)
    register_exception_handlers(app)

    @app.get("/raise/{code}")
    async def raise_route(code: str):  # pragma: no cover - body trivial
        raise DSAdapterError(f"forced {code}", code=code)

    @app.get("/boom")
    async def boom():  # pragma: no cover - body trivial
        raise RuntimeError("kaboom")

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("code", list(ERROR_CATALOG.keys()))
def test_handler_maps_each_code(client: TestClient, code: str) -> None:
    resp = client.get(f"/raise/{code}")
    spec = ERROR_CATALOG[code]
    assert resp.status_code == spec["status"]
    assert resp.headers["content-type"].startswith("application/fhir+json")
    body = resp.json()
    assert body["resourceType"] == "OperationOutcome"
    assert body["issue"][0]["details"]["coding"][0]["code"] == code
    assert "x-correlation-id" in {k.lower() for k in resp.headers.keys()}


def test_generic_exception_returns_gen_001(client: TestClient) -> None:
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["issue"][0]["details"]["coding"][0]["code"] == "GEN_001"
