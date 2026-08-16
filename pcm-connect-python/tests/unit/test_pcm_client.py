from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import jwt
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
async def test_get_token_uses_explicit_client_assertion_audience(es256_keypair) -> None:
    private_pem, _ = es256_keypair
    pcm = PCMClient(
        http=httpx.AsyncClient(),
        base_url="http://pcm-transport:4501",
        token_endpoint="/token",
        introspect_endpoint="/introspect",
        client_id="adapter-test",
        client_signing_key=private_pem,
        client_assertion_audience="https://pcm-public:4501/token",
    )
    route = respx.post("http://pcm-transport:4501/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 60})
    )

    await pcm.get_token()

    form = parse_qs(route.calls[0].request.content.decode())
    claims = jwt.decode(form["client_assertion"][0], options={"verify_signature": False})
    assert claims["aud"] == "https://pcm-public:4501/token"


@respx.mock
async def test_get_token_sends_configured_pcm_scope_and_omits_resource(es256_keypair) -> None:
    private_pem, _ = es256_keypair
    pcm = PCMClient(
        http=httpx.AsyncClient(),
        base_url="https://pcm",
        token_endpoint="/token",
        introspect_endpoint="/introspect",
        client_id="adapter-test",
        client_signing_key=private_pem,
        token_scope="consent.read consent.write fhir.read",
    )
    route = respx.post("https://pcm/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 60})
    )

    await pcm.get_token()

    form = parse_qs(route.calls[0].request.content.decode())
    assert form["scope"] == ["consent.read consent.write fhir.read"]
    assert "resource" not in form


@respx.mock
async def test_get_token_uses_production_scope_by_default(es256_keypair) -> None:
    pcm = _make_client(es256_keypair)
    route = respx.post("https://pcm/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_in": 60})
    )

    await pcm.get_token()

    form = parse_qs(route.calls[0].request.content.decode())
    assert form["scope"] == ["system/*.crus"]


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
async def test_get_token_200_non_json_gateway_error_maps_to_pcm_002(es256_keypair) -> None:
    pcm = _make_client(es256_keypair)
    respx.post("https://pcm/token").mock(
        return_value=httpx.Response(
            200,
            text="Support ID: test-only",
            headers={
                "content-type": "text/html; charset=UTF-8",
                "x-amzn-errortype": "ForbiddenException",
            },
        )
    )

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
