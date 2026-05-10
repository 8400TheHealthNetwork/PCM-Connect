from __future__ import annotations

import time
import uuid

import jwt


def mint_internal_jwt(
    *,
    issuer: str,
    audience: str,
    patient_id: str,
    consent_id: str | None,
    scope: str | None,
    baskets: list[str] | None,
    access_type: str | None,
    sp_organization_id: str | None,
    correlation_id: str,
    signing_key: str,
    expiry_seconds: int = 300,
    algorithm: str = "ES256",
) -> str:
    now = int(time.time())
    payload = {
        "iss": issuer,
        "sub": patient_id,
        "aud": audience,
        "exp": now + expiry_seconds,
        "iat": now,
        "consent_id": consent_id,
        "scope": scope,
        "patient": patient_id,
        "baskets": baskets or [],
        "access_type": access_type,
        "sp_organization_id": sp_organization_id,
        "correlation_id": correlation_id,
    }
    return jwt.encode(payload, signing_key, algorithm=algorithm)


def mint_client_assertion(
    *,
    client_id: str,
    audience: str,
    signing_key: str,
    ttl_seconds: int = 60,
    algorithm: str = "ES256",
) -> str:
    now = int(time.time())
    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": audience,
        "exp": now + ttl_seconds,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, signing_key, algorithm=algorithm)
