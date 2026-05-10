from __future__ import annotations

import httpx
import respx


@respx.mock
def test_forbidden_label_yields_400(client, sample_introspection_response, sample_fhir_bundle_with_v_label) -> None:
    respx.post("http://pcm.test/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 60})
    )
    respx.post("http://pcm.test/introspect").mock(
        return_value=httpx.Response(200, json=sample_introspection_response)
    )
    respx.post("http://id.test/api/v1/resolve").mock(
        return_value=httpx.Response(200, json={"patient_id": "P-9"})
    )
    respx.get("http://fhir.test/Observation").mock(
        return_value=httpx.Response(200, json=sample_fhir_bundle_with_v_label)
    )

    resp = client.get(
        "/fhir/Observation",
        headers={"Authorization": "Bearer opaque"},
    )

    assert resp.status_code == 400
    body = resp.json()
    assert body["resourceType"] == "OperationOutcome"
    # Generic — no leak of which label
    diag = body["issue"][0]["diagnostics"]
    assert "V" not in diag.split()
    assert "il-core-main-security-label" not in diag
