from __future__ import annotations

import time

import jwt as pyjwt

from src.auth.jwt_service import mint_client_assertion, mint_internal_jwt


def test_internal_jwt_claims_and_signature(es256_keypair: tuple[str, str]) -> None:
    private_pem, public_pem = es256_keypair
    token = mint_internal_jwt(
        issuer="ds-adapter",
        audience="https://fhir-internal:8080",
        patient_id="12345",
        consent_id="consent-1",
        scope="patient/Observation.rs",
        baskets=["basket-a"],
        access_type="treatment",
        sp_organization_id="org-hospital-a",
        correlation_id="cid-9",
        signing_key=private_pem,
        expiry_seconds=300,
    )

    decoded = pyjwt.decode(token, public_pem, algorithms=["ES256"], audience="https://fhir-internal:8080")
    assert decoded["iss"] == "ds-adapter"
    assert decoded["sub"] == "12345"
    assert decoded["patient"] == "12345"
    assert decoded["consent_id"] == "consent-1"
    assert decoded["scope"] == "patient/Observation.rs"
    assert decoded["baskets"] == ["basket-a"]
    assert decoded["access_type"] == "treatment"
    assert decoded["sp_organization_id"] == "org-hospital-a"
    assert decoded["correlation_id"] == "cid-9"
    assert decoded["exp"] - decoded["iat"] == 300


def test_client_assertion_signed_correctly(es256_keypair: tuple[str, str]) -> None:
    private_pem, public_pem = es256_keypair
    token = mint_client_assertion(
        client_id="adapter-1",
        audience="https://pcm/token",
        signing_key=private_pem,
    )
    decoded = pyjwt.decode(token, public_pem, algorithms=["ES256"], audience="https://pcm/token")
    assert decoded["iss"] == decoded["sub"] == "adapter-1"
    assert "jti" in decoded
    assert decoded["exp"] > decoded["iat"]


def test_internal_jwt_expiry_in_future(es256_keypair: tuple[str, str]) -> None:
    private_pem, public_pem = es256_keypair
    before = int(time.time())
    token = mint_internal_jwt(
        issuer="ds-adapter",
        audience="aud",
        patient_id="1",
        consent_id=None,
        scope=None,
        baskets=None,
        access_type=None,
        sp_organization_id=None,
        correlation_id="c",
        signing_key=private_pem,
        expiry_seconds=120,
    )
    decoded = pyjwt.decode(token, public_pem, algorithms=["ES256"], audience="aud")
    assert decoded["iat"] >= before
    assert decoded["exp"] - decoded["iat"] == 120
