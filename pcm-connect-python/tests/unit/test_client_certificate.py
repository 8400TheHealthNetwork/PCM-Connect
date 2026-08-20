from __future__ import annotations

from unittest.mock import Mock

from src.observability.client_certificate import from_aws_alb_headers


def test_extracts_safe_aws_alb_verify_mode_metadata() -> None:
    metadata = from_aws_alb_headers(
        {
            "X-Amzn-Mtls-Clientcert-Subject": "CN=org-123,OU=FHIR,O=Hospital,C=IL",
            "X-Amzn-Mtls-Clientcert-Issuer": "CN=MOH Client CA,O=MOH,C=IL",
            "X-Amzn-Mtls-Clientcert-Serial-Number": "03:a5:b1",
            "X-Amzn-Mtls-Clientcert-Validity": (
                "NotBefore=2026-01-01T00:00:00Z;NotAfter=2027-01-01T00:00:00Z"
            ),
            "X-Amzn-Mtls-Clientcert-Leaf": "-----BEGIN%20CERTIFICATE-----%0ASECRET",
        }
    )

    assert metadata is not None
    assert metadata.common_names == ("org-123",)
    assert metadata.serial_number == "03A5B1"
    assert metadata.not_before == "2026-01-01T00:00:00Z"
    assert metadata.not_after == "2027-01-01T00:00:00Z"
    assert "certificate" not in metadata.span_attributes()
    assert all("SECRET" not in str(value) for value in metadata.span_attributes().values())


def test_ignores_missing_or_malformed_metadata() -> None:
    assert from_aws_alb_headers({}) is None
    metadata = from_aws_alb_headers(
        {
            "X-Amzn-Mtls-Clientcert-Serial-Number": "not-hex",
            "X-Amzn-Mtls-Clientcert-Validity": "NotBefore=nope;NotAfter=also-nope",
        }
    )
    assert metadata is None


def test_attaches_ecs_and_otel_attributes_to_recording_span() -> None:
    metadata = from_aws_alb_headers(
        {
            "X-Amzn-Mtls-Clientcert-Subject": "CN=org-123,O=Hospital,C=IL",
            "X-Amzn-Mtls-Clientcert-Issuer": "CN=MOH Client CA,O=MOH,C=IL",
            "X-Amzn-Mtls-Clientcert-Serial-Number": "A1B2",
        }
    )
    assert metadata is not None
    span = Mock()
    span.is_recording.return_value = True

    metadata.attach_to_span(span)

    attributes = dict(call.args for call in span.set_attribute.call_args_list)
    assert attributes["tls.client.subject"] == "CN=org-123,O=Hospital,C=IL"
    assert attributes["tls.client.x509.subject.common_name"] == ("org-123",)
    assert attributes["tls.client.x509.serial_number"] == "A1B2"
