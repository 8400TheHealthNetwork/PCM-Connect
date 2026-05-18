"""Discovery metadata for the adapter when acting as the auth server
trusted by an internal FHIR resource server (e.g. IRIS).

Single source of truth: `JWTConfig.issuer` is both the JWT `iss` claim and
the `issuer` URL advertised here. `jwks_uri` defaults to
`<issuer>/.well-known/jwks.json` unless explicitly overridden.
"""
from __future__ import annotations

from typing import Any

from src.config.models import AppConfig


def _jwks_uri(config: AppConfig) -> str:
    if config.metadata.jwks_uri:
        return config.metadata.jwks_uri
    return config.jwt.issuer.rstrip("/") + "/.well-known/jwks.json"


def build_oauth_authorization_server(config: AppConfig) -> dict[str, Any]:
    """RFC 8414 — /.well-known/oauth-authorization-server."""
    md = config.metadata
    payload: dict[str, Any] = {
        "issuer": config.jwt.issuer,
        "jwks_uri": _jwks_uri(config),
        "response_types_supported": list(md.response_types_supported),
        "grant_types_supported": list(md.grant_types_supported),
        "token_endpoint_auth_methods_supported": list(
            md.token_endpoint_auth_methods_supported
        ),
        "id_token_signing_alg_values_supported": [config.jwt.algorithm],
        "code_challenge_methods_supported": list(md.code_challenge_methods_supported),
    }
    if md.authorization_endpoint:
        payload["authorization_endpoint"] = md.authorization_endpoint
    if md.token_endpoint:
        payload["token_endpoint"] = md.token_endpoint
    if md.introspection_endpoint:
        payload["introspection_endpoint"] = md.introspection_endpoint
    if md.scopes_supported:
        payload["scopes_supported"] = list(md.scopes_supported)
    return payload


def build_openid_configuration(config: AppConfig) -> dict[str, Any]:
    """OIDC discovery — same body as the OAuth one for our purposes,
    plus a couple of OIDC-specific fields some clients require."""
    payload = build_oauth_authorization_server(config)
    payload.setdefault("subject_types_supported", ["public"])
    return payload


def build_smart_configuration(config: AppConfig) -> dict[str, Any]:
    """SMART on FHIR /.well-known/smart-configuration."""
    payload = build_oauth_authorization_server(config)
    payload["capabilities"] = list(config.metadata.capabilities)
    return payload
