from __future__ import annotations

import httpx
import respx


def _err_code(resp) -> str:
    return resp.json()["issue"][0]["details"]["coding"][0]["code"]


@respx.mock
def test_introspection_inactive_returns_auth_002(client) -> None:
    respx.post("http://pcm.test/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 60})
    )
    respx.post("http://pcm.test/introspect").mock(
        return_value=httpx.Response(200, json={"active": False})
    )

    resp = client.get("/fhir/Observation", headers={"Authorization": "Bearer opaque"})
    assert resp.status_code == 401
    assert _err_code(resp) == "AUTH_002"


@respx.mock
def test_introspection_inactive_with_past_exp_returns_auth_003(client) -> None:
    respx.post("http://pcm.test/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 60})
    )
    respx.post("http://pcm.test/introspect").mock(
        return_value=httpx.Response(200, json={"active": False, "exp": 1})
    )

    resp = client.get("/fhir/Observation", headers={"Authorization": "Bearer opaque"})
    assert resp.status_code == 401
    assert _err_code(resp) == "AUTH_003"


@respx.mock
def test_pcm_token_unreachable_returns_pcm_001(client) -> None:
    respx.post("http://pcm.test/token").mock(side_effect=httpx.ConnectError("down"))

    resp = client.get("/fhir/Observation", headers={"Authorization": "Bearer opaque"})
    assert resp.status_code == 502
    assert _err_code(resp) == "PCM_001"


@respx.mock
def test_pcm_token_4xx_returns_pcm_002(client) -> None:
    respx.post("http://pcm.test/token").mock(return_value=httpx.Response(401))

    resp = client.get("/fhir/Observation", headers={"Authorization": "Bearer opaque"})
    assert resp.status_code == 401
    assert _err_code(resp) == "PCM_002"
