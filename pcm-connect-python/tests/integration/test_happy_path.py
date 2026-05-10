from __future__ import annotations

import httpx
import respx


@respx.mock
def test_full_flow_returns_bundle(client, sample_introspection_response, sample_fhir_bundle) -> None:
    respx.post("http://pcm.test/token").mock(
        return_value=httpx.Response(200, json={"access_token": "adapter-tok", "expires_in": 60})
    )
    respx.post("http://pcm.test/introspect").mock(
        return_value=httpx.Response(200, json=sample_introspection_response)
    )
    respx.post("http://id.test/api/v1/resolve").mock(
        return_value=httpx.Response(200, json={"patient_id": "P-42"})
    )
    fhir_route = respx.get("http://fhir.test/Observation").mock(
        return_value=httpx.Response(200, json=sample_fhir_bundle, headers={"content-type": "application/fhir+json"})
    )

    resp = client.get(
        "/fhir/Observation",
        params={"patient": "000000018"},
        headers={"Authorization": "Bearer opaque-xyz", "X-Correlation-ID": "trace-1"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers["x-correlation-id"] == "trace-1"
    assert resp.json()["resourceType"] == "Bundle"

    # FHIR call received our minted JWT, not the original opaque token
    forwarded = fhir_route.calls[0].request
    assert forwarded.headers["authorization"].startswith("Bearer ")
    assert forwarded.headers["authorization"] != "Bearer opaque-xyz"
    assert forwarded.headers["x-correlation-id"] == "trace-1"


@respx.mock
def test_missing_bearer_returns_auth_001(client) -> None:
    resp = client.get("/fhir/Observation")
    assert resp.status_code == 401
    body = resp.json()
    assert body["issue"][0]["details"]["coding"][0]["code"] == "AUTH_001"


@respx.mock
def test_malformed_bearer_returns_auth_001(client) -> None:
    resp = client.get("/fhir/Observation", headers={"Authorization": "Basic abc"})
    assert resp.status_code == 401
    assert resp.json()["issue"][0]["details"]["coding"][0]["code"] == "AUTH_001"
