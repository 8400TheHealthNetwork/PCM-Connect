from __future__ import annotations

import httpx
import respx


@respx.mock
def test_ready_when_all_dependencies_respond(client) -> None:
    respx.head("http://pcm.test").mock(return_value=httpx.Response(200))
    respx.head("http://fhir.test").mock(return_value=httpx.Response(200))

    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["pcm"] == "ok"
    assert body["fhir_server"] == "ok"


@respx.mock
def test_not_ready_when_dependency_down(client) -> None:
    respx.head("http://pcm.test").mock(return_value=httpx.Response(200))
    respx.head("http://fhir.test").mock(side_effect=httpx.ConnectError("down"))

    resp = client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["fhir_server"] == "error"
    assert body["pcm"] == "ok"
