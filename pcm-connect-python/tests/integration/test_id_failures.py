from __future__ import annotations

import httpx
import respx


def _err_code(resp) -> str:
    return resp.json()["issue"][0]["details"]["coding"][0]["code"]


def _wire_pcm(introspection_response: dict) -> None:
    respx.post("http://pcm.test/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 60})
    )
    respx.post("http://pcm.test/introspect").mock(
        return_value=httpx.Response(200, json=introspection_response)
    )


@respx.mock
def test_id_replacement_404_returns_id_002(client, sample_introspection_response) -> None:
    _wire_pcm(sample_introspection_response)
    respx.post("http://id.test/api/v1/resolve").mock(return_value=httpx.Response(404))

    resp = client.get("/fhir/Observation", headers={"Authorization": "Bearer opaque"})
    assert resp.status_code == 404
    assert _err_code(resp) == "ID_002"


@respx.mock
def test_id_replacement_unreachable_returns_id_001(client, sample_introspection_response) -> None:
    _wire_pcm(sample_introspection_response)
    respx.post("http://id.test/api/v1/resolve").mock(side_effect=httpx.ConnectError("down"))

    resp = client.get("/fhir/Observation", headers={"Authorization": "Bearer opaque"})
    assert resp.status_code == 502
    assert _err_code(resp) == "ID_001"
