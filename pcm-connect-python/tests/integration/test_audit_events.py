from __future__ import annotations

import json

import httpx
import respx

from src.audit.service import AuditService


class _CaptureTarget:
    def __init__(self) -> None:
        self.payloads: list[str] = []

    async def start(self) -> None:
        return None

    async def send(self, payload: str) -> None:
        self.payloads.append(payload)

    async def aclose(self) -> None:
        return None


def _capture_audit(app) -> _CaptureTarget:
    target = _CaptureTarget()
    app.state.audit_service = AuditService(targets=[target], formatter="ecs", enabled=True)
    return target


def _wire_pcm(introspection_response: dict) -> None:
    respx.post("http://pcm.test/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 60})
    )
    respx.post("http://pcm.test/introspect").mock(
        return_value=httpx.Response(200, json=introspection_response)
    )


def test_handled_auth_failure_has_error_outcome_and_duration(app, client) -> None:
    target = _capture_audit(app)

    response = client.get("/fhir/Observation", headers={"X-Correlation-ID": "cid-auth"})

    assert response.status_code == 401
    assert len(target.payloads) == 1
    event = json.loads(target.payloads[0])
    assert event["event"]["outcome"] == "failure"
    assert event["event"]["action"] == "fhir_search"
    assert event["pcm"]["audit"]["processing_stage"] == "bearer_validation"
    assert event["event"]["duration"] > 0
    assert event["error"]["code"] == "AUTH_001"
    assert event["labels"]["correlation_id"] == "cid-auth"
    assert event["pcm"]["authorization"] == {
        "decision": "denied",
        "stage": "bearer_validation",
    }


@respx.mock
def test_pcm_client_auth_failure_is_indeterminate(app, client) -> None:
    target = _capture_audit(app)
    respx.post("http://pcm.test/token").mock(return_value=httpx.Response(401))

    response = client.get(
        "/fhir/Observation",
        headers={"Authorization": "Bearer opaque"},
    )

    assert response.status_code == 401
    event = json.loads(target.payloads[0])
    assert event["error"]["code"] == "PCM_002"
    assert event["pcm"]["audit"]["processing_stage"] == "pcm_introspection"
    assert event["pcm"]["authorization"] == {
        "decision": "indeterminate",
        "stage": "pcm_introspection",
    }


@respx.mock
def test_inactive_token_is_denied_during_introspection(app, client) -> None:
    target = _capture_audit(app)
    _wire_pcm({"active": False})

    response = client.get(
        "/fhir/Observation",
        headers={"Authorization": "Bearer inactive"},
    )

    assert response.status_code == 401
    event = json.loads(target.payloads[0])
    assert event["error"]["code"] == "AUTH_002"
    assert event["pcm"]["audit"]["processing_stage"] == "pcm_introspection"
    assert event["pcm"]["authorization"] == {
        "decision": "denied",
        "stage": "pcm_introspection",
    }


@respx.mock
def test_expired_token_is_denied_during_introspection(app, client) -> None:
    target = _capture_audit(app)
    _wire_pcm({"active": False, "exp": 0})

    response = client.get(
        "/fhir/Observation",
        headers={"Authorization": "Bearer expired"},
    )

    assert response.status_code == 401
    event = json.loads(target.payloads[0])
    assert event["error"]["code"] == "AUTH_003"
    assert event["pcm"]["authorization"]["decision"] == "denied"


@respx.mock
def test_downstream_failure_retains_pcm_and_trusted_client_certificate(
    app, client, sample_introspection_response
) -> None:
    target = _capture_audit(app)
    app.state.config.inbound_mtls.trust_aws_alb_headers = True
    app.state.config.proxy_headers.trusted_hops = 1
    _wire_pcm(sample_introspection_response)
    respx.post("http://id.test/api/v1/resolve").mock(return_value=httpx.Response(404))

    response = client.get(
        "/fhir/Observation",
        headers={
            "Authorization": "Bearer opaque",
            "X-Amzn-Mtls-Clientcert-Subject": "CN=org-123,OU=FHIR,O=Hospital,C=IL",
            "X-Amzn-Mtls-Clientcert-Issuer": "CN=MOH Client CA,O=MOH,C=IL",
            "X-Amzn-Mtls-Clientcert-Serial-Number": "03A5B1",
            "X-Amzn-Mtls-Clientcert-Validity": (
                "NotBefore=2026-01-01T00:00:00Z;NotAfter=2027-01-01T00:00:00Z"
            ),
            "X-Amzn-Mtls-Clientcert-Leaf": "-----BEGIN%20CERTIFICATE-----%0ASECRET",
            "X-Forwarded-For": "192.0.2.250, 198.51.100.20",
        },
    )

    assert response.status_code == 404
    event = json.loads(target.payloads[0])
    assert event["error"]["code"] == "ID_002"
    assert event["pcm"]["scope"] == sample_introspection_response["scope"]
    assert event["pcm"]["consent_id"] == sample_introspection_response["consent_id"]
    assert event["pcm"]["sp_organization_id"] == "org-hospital-a"
    assert event["pcm"]["patient_id"] == "*****0018"
    assert event["pcm"]["baskets"] == ["basket-a"]
    assert event["pcm"]["access_type"] == "treatment"
    assert event["pcm"]["authorization"] == {
        "decision": "allowed",
        "stage": "authorized",
    }
    assert event["pcm"]["audit"]["processing_stage"] == "identity_resolution"
    assert event["source"]["ip"] == "198.51.100.20"
    assert event["tls"]["client"]["subject"].startswith("CN=org-123")
    assert event["tls"]["client"]["x509"]["subject"]["common_name"] == ["org-123"]
    assert event["tls"]["client"]["x509"]["serial_number"] == "03A5B1"
    assert "SECRET" not in target.payloads[0]


@respx.mock
def test_success_has_fhir_context_pcm_authorization_and_completed_stage(
    app, client, sample_introspection_response, sample_fhir_bundle
) -> None:
    target = _capture_audit(app)
    _wire_pcm(sample_introspection_response)
    respx.post("http://id.test/api/v1/resolve").mock(
        return_value=httpx.Response(200, json={"patient_id": "P-42"})
    )
    respx.get("http://fhir.test/Observation").mock(
        return_value=httpx.Response(200, json=sample_fhir_bundle)
    )

    response = client.get(
        "/fhir/Observation",
        headers={"Authorization": "Bearer opaque"},
    )

    assert response.status_code == 200
    event = json.loads(target.payloads[0])
    assert event["event"]["action"] == "fhir_search"
    assert event["pcm"]["audit"]["processing_stage"] == "completed"
    assert event["pcm"]["fhir"] == {
        "resource_type": "Observation",
        "interaction": "search",
    }
    assert event["pcm"]["audit"]["schema_version"] == "1.0.0"
    assert event["pcm"]["authorization"] == {
        "decision": "allowed",
        "stage": "authorized",
    }
    assert event["pcm"]["baskets"] == ["basket-a"]
    assert event["pcm"]["access_type"] == "treatment"


@respx.mock
def test_downstream_denial_does_not_rewrite_pcm_authorization_decision(
    app, client, sample_introspection_response
) -> None:
    target = _capture_audit(app)
    _wire_pcm(sample_introspection_response)
    respx.post("http://id.test/api/v1/resolve").mock(
        return_value=httpx.Response(200, json={"patient_id": "P-42"})
    )
    respx.get("http://fhir.test/Observation").mock(
        return_value=httpx.Response(403, json={"resourceType": "OperationOutcome"})
    )

    response = client.get(
        "/fhir/Observation",
        headers={"Authorization": "Bearer opaque"},
    )

    assert response.status_code == 403
    event = json.loads(target.payloads[0])
    assert event["event"]["outcome"] == "failure"
    assert event["pcm"]["authorization"]["decision"] == "allowed"
    assert event["pcm"]["audit"]["processing_stage"] == "completed"


@respx.mock
def test_alb_certificate_headers_are_not_forwarded_to_fhir(
    app, client, sample_introspection_response, sample_fhir_bundle
) -> None:
    _wire_pcm(sample_introspection_response)
    respx.post("http://id.test/api/v1/resolve").mock(
        return_value=httpx.Response(200, json={"patient_id": "P-42"})
    )
    fhir_route = respx.get("http://fhir.test/Observation").mock(
        return_value=httpx.Response(200, json=sample_fhir_bundle)
    )

    response = client.get(
        "/fhir/Observation",
        headers={
            "Authorization": "Bearer opaque",
            "X-Amzn-Mtls-Clientcert-Subject": "CN=org-123,O=Hospital,C=IL",
            "X-Amzn-Mtls-Clientcert-Leaf": "certificate-material",
        },
    )

    assert response.status_code == 200
    forwarded_headers = fhir_route.calls[0].request.headers
    assert "x-amzn-mtls-clientcert-subject" not in forwarded_headers
    assert "x-amzn-mtls-clientcert-leaf" not in forwarded_headers
