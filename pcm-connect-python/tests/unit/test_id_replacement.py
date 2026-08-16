from __future__ import annotations

import json

import httpx
import pytest
import respx

from src.config.models import IDReplacementConfig
from src.errors import DSAdapterError
from src.identity.id_replacement import IDReplacementClient


def _config(**overrides) -> IDReplacementConfig:
    base = dict(
        base_url="http://id",
        endpoint="/api/v1/resolve",
        timeout_seconds=1.0,
        retries=3,
        retry_backoff_seconds=0.0,
    )
    base.update(overrides)
    return IDReplacementConfig(**base)


def _client() -> IDReplacementClient:
    return IDReplacementClient(http=httpx.AsyncClient(), config=_config())


@respx.mock
async def test_resolve_success() -> None:
    route = respx.post("http://id/api/v1/resolve").mock(
        return_value=httpx.Response(200, json={"patient_id": "P-42", "resource_reference": "Patient/P-42"})
    )

    result = await _client().resolve_patient_id("000000018")

    assert result == "P-42"
    assert json.loads(route.calls[0].request.content) == {
        "identifier": {
            "system": "http://fhir.health.gov.il/identifier/il-national-id",
            "value": "000000018",
        }
    }


@respx.mock
async def test_resolve_404_returns_id_002() -> None:
    respx.post("http://id/api/v1/resolve").mock(return_value=httpx.Response(404, json={"error": "patient_not_found"}))

    with pytest.raises(DSAdapterError) as exc_info:
        await _client().resolve_patient_id("nope")
    assert exc_info.value.code == "ID_002"


@respx.mock
async def test_resolve_retries_on_timeout_then_succeeds() -> None:
    route = respx.post("http://id/api/v1/resolve").mock(
        side_effect=[
            httpx.TimeoutException("slow"),
            httpx.TimeoutException("slow"),
            httpx.Response(200, json={"patient_id": "P-7"}),
        ]
    )

    result = await _client().resolve_patient_id("000000018")
    assert result == "P-7"
    assert route.call_count == 3


@respx.mock
async def test_resolve_all_retries_fail_returns_id_001() -> None:
    route = respx.post("http://id/api/v1/resolve").mock(side_effect=httpx.ConnectError("down"))

    client = IDReplacementClient(
        http=httpx.AsyncClient(),
        config=_config(retries=3),
    )
    with pytest.raises(DSAdapterError) as exc_info:
        await client.resolve_patient_id("000000018")
    assert exc_info.value.code == "ID_001"
    assert route.call_count == 3


@respx.mock
async def test_resolve_5xx_retries_then_id_001() -> None:
    route = respx.post("http://id/api/v1/resolve").mock(return_value=httpx.Response(503))

    with pytest.raises(DSAdapterError) as exc_info:
        await _client().resolve_patient_id("000000018")
    assert exc_info.value.code == "ID_001"
    assert route.call_count == 3


@respx.mock
async def test_resolve_200_without_patient_id_is_id_001() -> None:
    respx.post("http://id/api/v1/resolve").mock(return_value=httpx.Response(200, json={"weird": "shape"}))

    with pytest.raises(DSAdapterError) as exc_info:
        await _client().resolve_patient_id("000000018")
    assert exc_info.value.code == "ID_001"
