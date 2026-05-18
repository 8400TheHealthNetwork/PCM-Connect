from __future__ import annotations

import jwt as pyjwt

from src.auth.jwks import build_jwks, get_signing_kid
from src.auth.jwt_service import mint_internal_jwt
from src.auth.metadata import (
    build_oauth_authorization_server,
    build_openid_configuration,
    build_smart_configuration,
)
from src.config.models import (
    AppConfig,
    FHIRServerConfig,
    IDReplacementConfig,
    JWTConfig,
    MetadataConfig,
    PCMConfig,
)


def _make_config(
    *,
    issuer: str = "https://adapter.example.com",
    audience: str | None = None,
    metadata: MetadataConfig | None = None,
) -> AppConfig:
    return AppConfig(
        pcm=PCMConfig(base_url="https://pcm:3000"),
        fhir_server=FHIRServerConfig(base_url="https://fhir-internal:8080"),
        id_replacement=IDReplacementConfig(base_url="http://id-service:9000"),
        jwt=JWTConfig(issuer=issuer, audience=audience),
        metadata=metadata or MetadataConfig(),
    )


# --- discovery payload shape -----------------------------------------------


def test_oauth_metadata_uses_jwt_issuer_as_issuer() -> None:
    cfg = _make_config(issuer="https://adapter.example.com")
    md = build_oauth_authorization_server(cfg)
    assert md["issuer"] == "https://adapter.example.com"
    assert md["jwks_uri"] == "https://adapter.example.com/.well-known/jwks.json"


def test_oauth_metadata_jwks_uri_override() -> None:
    cfg = _make_config(metadata=MetadataConfig(jwks_uri="https://elsewhere/jwks.json"))
    md = build_oauth_authorization_server(cfg)
    assert md["jwks_uri"] == "https://elsewhere/jwks.json"


def test_oauth_metadata_advertises_signing_alg() -> None:
    cfg = _make_config()
    md = build_oauth_authorization_server(cfg)
    assert md["id_token_signing_alg_values_supported"] == [cfg.jwt.algorithm]


def test_oauth_metadata_omits_optional_endpoints_when_unset() -> None:
    cfg = _make_config()
    md = build_oauth_authorization_server(cfg)
    assert "authorization_endpoint" not in md
    assert "token_endpoint" not in md
    assert "introspection_endpoint" not in md


def test_oauth_metadata_includes_optional_endpoints_when_set() -> None:
    cfg = _make_config(
        metadata=MetadataConfig(
            authorization_endpoint="https://pcm/authorize",
            token_endpoint="https://pcm/token",
            introspection_endpoint="https://pcm/introspect",
            scopes_supported=["patient/Observation.rs"],
        )
    )
    md = build_oauth_authorization_server(cfg)
    assert md["authorization_endpoint"] == "https://pcm/authorize"
    assert md["token_endpoint"] == "https://pcm/token"
    assert md["introspection_endpoint"] == "https://pcm/introspect"
    assert md["scopes_supported"] == ["patient/Observation.rs"]


def test_openid_configuration_adds_subject_types() -> None:
    cfg = _make_config()
    md = build_openid_configuration(cfg)
    assert md["subject_types_supported"] == ["public"]


def test_smart_configuration_includes_capabilities() -> None:
    cfg = _make_config(metadata=MetadataConfig(capabilities=["launch-standalone"]))
    md = build_smart_configuration(cfg)
    assert md["capabilities"] == ["launch-standalone"]


# --- JWT header now carries `kid` matching the JWKS ------------------------


def test_internal_jwt_header_kid_matches_published_jwks(es256_keypair) -> None:
    private_pem, public_pem = es256_keypair
    kid = get_signing_kid(private_pem, "ES256")
    published_kid = build_jwks(private_pem, "ES256")["keys"][0]["kid"]
    assert kid == published_kid

    token = mint_internal_jwt(
        issuer="https://adapter.example.com",
        audience="https://fhir-internal:8080",
        patient_id="1",
        consent_id=None,
        scope=None,
        baskets=None,
        access_type=None,
        sp_organization_id=None,
        correlation_id="c",
        signing_key=private_pem,
        kid=kid,
    )
    headers = pyjwt.get_unverified_header(token)
    assert headers["kid"] == kid


def test_internal_jwt_no_kid_when_not_supplied(es256_keypair) -> None:
    private_pem, _ = es256_keypair
    token = mint_internal_jwt(
        issuer="https://adapter.example.com",
        audience="aud",
        patient_id="1",
        consent_id=None,
        scope=None,
        baskets=None,
        access_type=None,
        sp_organization_id=None,
        correlation_id="c",
        signing_key=private_pem,
    )
    headers = pyjwt.get_unverified_header(token)
    assert "kid" not in headers


# --- audience as list ------------------------------------------------------


def test_internal_jwt_supports_list_audience(es256_keypair) -> None:
    private_pem, public_pem = es256_keypair
    audiences = [
        "https://iris.example.com:443/csp/healthshare/fhir1/fhir/r4",
        "https://iris.example.com/csp/healthshare/fhir1/fhir/r4",
    ]
    token = mint_internal_jwt(
        issuer="https://adapter.example.com",
        audience=audiences,
        patient_id="1",
        consent_id=None,
        scope=None,
        baskets=None,
        access_type=None,
        sp_organization_id=None,
        correlation_id="c",
        signing_key=private_pem,
    )
    # Either audience must verify; PyJWT accepts when the verifier's audience
    # appears anywhere in the token's `aud` array.
    for aud in audiences:
        decoded = pyjwt.decode(token, public_pem, algorithms=["ES256"], audience=aud)
        assert decoded["aud"] == audiences


def test_jwt_config_csv_audience_split() -> None:
    # Env-var style override: comma-separated string becomes a list.
    cfg = JWTConfig(audience="https://a/fhir,https://b/fhir")
    assert cfg.audience == ["https://a/fhir", "https://b/fhir"]


def test_jwt_config_single_string_audience_preserved() -> None:
    cfg = JWTConfig(audience="https://a/fhir")
    assert cfg.audience == "https://a/fhir"


def test_jwt_config_list_audience_preserved() -> None:
    cfg = JWTConfig(audience=["https://a/fhir", "https://b/fhir"])
    assert cfg.audience == ["https://a/fhir", "https://b/fhir"]


# --- default scopes_supported is broad enough for many baskets -------------


def test_metadata_default_scopes_cover_common_resources() -> None:
    cfg = _make_config()
    md = build_oauth_authorization_server(cfg)
    scopes = md.get("scopes_supported") or []
    assert "patient/*.rs" in scopes
    assert "patient/Observation.rs" in scopes
    assert "patient/Condition.rs" in scopes
    assert "patient/MedicationRequest.rs" in scopes
    assert "system/*.rs" in scopes
    # Sanity: plenty of resources advertised.
    assert len([s for s in scopes if s.startswith("patient/")]) > 20
