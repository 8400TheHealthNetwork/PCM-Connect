from __future__ import annotations

import httpx
import pytest
import respx

from src.auth.pcm_client import PCMClient
from src.errors import DSAdapterError


def _make_client(es256_keypair: tuple[str, str]) -> PCMClient:
    private_pem, _ = es256_keypair
    return PCMClient(
        http=httpx.AsyncClient(),
        base_url="https://pcm",
        token_endpoint="/token",
        introspect_endpoint="/introspect",
        client_id="adapter-test",
        client_signing_key=private_pem,
    )


@respx.mock
async def test_get_token_success(es256_keypair) -> None:
    pcm = _make_client(es256_keypair)
    respx.post("https://pcm/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 60})
    )

    token = await pcm.get_token()
    assert token == "tok-1"


@respx.mock
async def test_get_token_caches(es256_keypair) -> None:
    pcm = _make_client(es256_keypair)
    route = respx.post("https://pcm/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-cache", "expires_in": 600})
    )

    a = await pcm.get_token()
    b = await pcm.get_token()
    assert a == b == "tok-cache"
    assert route.call_count == 1


@respx.mock
async def test_get_token_pcm_unreachable_maps_to_pcm_001(es256_keypair) -> None:
    pcm = _make_client(es256_keypair)
    respx.post("https://pcm/token").mock(side_effect=httpx.ConnectError("nope"))

    with pytest.raises(DSAdapterError) as exc_info:
        await pcm.get_token()
    assert exc_info.value.code == "PCM_001"


@respx.mock
async def test_get_token_pcm_4xx_maps_to_pcm_002(es256_keypair) -> None:
    pcm = _make_client(es256_keypair)
    respx.post("https://pcm/token").mock(return_value=httpx.Response(401))

    with pytest.raises(DSAdapterError) as exc_info:
        await pcm.get_token()
    assert exc_info.value.code == "PCM_002"


@respx.mock
async def test_introspect_active(es256_keypair) -> None:
    pcm = _make_client(es256_keypair)
    respx.post("https://pcm/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 60})
    )
    respx.post("https://pcm/introspect").mock(
        return_value=httpx.Response(
            200,
            json={
                "active": True,
                "patient": "000000018",
                "scope": "patient/Observation.rs",
                "consent_id": "c1",
                "baskets": ["b1"],
                "access_type": "treatment",
                "sp_organization_id": "org-a",
            },
        )
    )

    result = await pcm.introspect("opaque-xyz")
    assert result.active is True
    assert result.patient == "000000018"
    assert result.consent_id == "c1"


@respx.mock
async def test_introspect_inactive_maps_to_auth_002(es256_keypair) -> None:
    pcm = _make_client(es256_keypair)
    respx.post("https://pcm/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 60})
    )
    respx.post("https://pcm/introspect").mock(
        return_value=httpx.Response(200, json={"active": False})
    )

    with pytest.raises(DSAdapterError) as exc_info:
        await pcm.introspect("opaque")
    assert exc_info.value.code == "AUTH_002"


@respx.mock
async def test_introspect_inactive_with_past_exp_maps_to_auth_003(es256_keypair) -> None:
    pcm = _make_client(es256_keypair)
    respx.post("https://pcm/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 60})
    )
    respx.post("https://pcm/introspect").mock(
        return_value=httpx.Response(200, json={"active": False, "exp": 1})
    )

    with pytest.raises(DSAdapterError) as exc_info:
        await pcm.introspect("opaque")
    assert exc_info.value.code == "AUTH_003"


@respx.mock
async def test_introspect_pcm_5xx_maps_to_pcm_001(es256_keypair) -> None:
    pcm = _make_client(es256_keypair)
    respx.post("https://pcm/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 60})
    )
    respx.post("https://pcm/introspect").mock(return_value=httpx.Response(503))

    with pytest.raises(DSAdapterError) as exc_info:
        await pcm.introspect("opaque")
    assert exc_info.value.code == "PCM_001"
