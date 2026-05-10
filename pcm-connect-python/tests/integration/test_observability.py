from __future__ import annotations

import httpx
import respx
from fastapi.testclient import TestClient


def test_metrics_endpoint_exposes_prometheus_text(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    # Each metric we declared must appear in the exposition text
    for name in (
        "ds_adapter_requests_total",
        "ds_adapter_request_duration_seconds",
        "ds_adapter_pcm_introspection_duration_seconds",
        "ds_adapter_id_replacement_duration_seconds",
        "ds_adapter_fhir_forward_duration_seconds",
        "ds_adapter_errors_total",
    ):
        assert name in body


def test_health_request_increments_counter(client: TestClient) -> None:
    client.get("/health")
    resp = client.get("/metrics")
    assert "ds_adapter_requests_total" in resp.text


@respx.mock
def test_error_increments_errors_total(client: TestClient) -> None:
    # No bearer → AUTH_001 → counter increments
    client.get("/fhir/Observation")
    resp = client.get("/metrics")
    assert 'ds_adapter_errors_total{error_code="AUTH_001"}' in resp.text
