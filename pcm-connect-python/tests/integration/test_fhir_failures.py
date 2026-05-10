from __future__ import annotations

import httpx
import respx


def _err_code(resp) -> str:
    return resp.json()["issue"][0]["details"]["coding"][0]["code"]


def _wire_upstream(sample_introspection_response: dict) -> None:
    respx.post("http://pcm.test/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 60})
    )
    respx.post("http://pcm.test/introspect").mock(
        return_value=httpx.Response(200, json=sample_introspection_response)
    )
    respx.post("http://id.test/api/v1/resolve").mock(
        return_value=httpx.Response(200, json={"patient_id": "P-1"})
    )


@respx.mock
def test_fhir_timeout_returns_fhir_002(client, sample_introspection_response) -> None:
    _wire_upstream(sample_introspection_response)
    respx.get("http://fhir.test/Observation").mock(side_effect=httpx.TimeoutException("slow"))

    resp = client.get("/fhir/Observation", headers={"Authorization": "Bearer opaque"})
    assert resp.status_code == 504
    assert _err_code(resp) == "FHIR_002"


@respx.mock
def test_fhir_connection_error_returns_fhir_001(client, sample_introspection_response) -> None:
    _wire_upstream(sample_introspection_response)
    respx.get("http://fhir.test/Observation").mock(side_effect=httpx.ConnectError("down"))

    resp = client.get("/fhir/Observation", headers={"Authorization": "Bearer opaque"})
    assert resp.status_code == 502
    assert _err_code(resp) == "FHIR_001"
