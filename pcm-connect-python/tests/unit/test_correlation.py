from __future__ import annotations

import re
import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.middleware.correlation import CORRELATION_HEADER, CorrelationMiddleware


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)

    @app.get("/echo")
    async def echo(request: Request) -> dict:
        return {"id": request.state.correlation_id}

    return TestClient(app)


def test_uses_supplied_correlation_id(client: TestClient) -> None:
    incoming = "supplied-id-1234"
    resp = client.get("/echo", headers={CORRELATION_HEADER: incoming})
    assert resp.status_code == 200
    assert resp.json()["id"] == incoming
    assert resp.headers[CORRELATION_HEADER] == incoming


def test_generates_when_missing(client: TestClient) -> None:
    resp = client.get("/echo")
    assert resp.status_code == 200
    generated = resp.headers[CORRELATION_HEADER]
    # Must be a valid uuid
    parsed = uuid.UUID(generated)
    assert str(parsed) == generated
    assert resp.json()["id"] == generated


def test_propagates_to_response_for_failures() -> None:
    from src.errors import DSAdapterError
    from src.errors.handlers import register_exception_handlers

    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)
    register_exception_handlers(app)

    @app.get("/explode")
    async def explode():  # pragma: no cover - trivial
        raise DSAdapterError("nope", code="AUTH_001")

    tc = TestClient(app, raise_server_exceptions=False)
    resp = tc.get("/explode", headers={CORRELATION_HEADER: "trace-7"})
    assert resp.status_code == 401
    assert resp.headers[CORRELATION_HEADER] == "trace-7"
