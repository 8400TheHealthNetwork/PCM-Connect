from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa


_EC_CURVE_TO_JWK = {
    "secp256r1": "P-256",
    "secp384r1": "P-384",
    "secp521r1": "P-521",
}


def load_signing_key_pem(value: str) -> str:
    """Accept either a PEM blob or a file path; return PEM contents."""
    if value.lstrip().startswith("-----BEGIN"):
        return value
    return Path(value).read_text(encoding="utf-8")


def build_jwks(signing_key_pem: str, algorithm: str) -> dict[str, Any]:
    """Derive a single-key JWKS from a PEM-encoded private signing key.

    The private material never leaves this function — only the public
    components (and a thumbprint-based `kid`) are serialised.
    """
    private_key = serialization.load_pem_private_key(
        signing_key_pem.encode("utf-8"), password=None
    )
    public_key = private_key.public_key()

    if isinstance(public_key, ec.EllipticCurvePublicKey):
        curve_name = public_key.curve.name
        crv = _EC_CURVE_TO_JWK.get(curve_name)
        if crv is None:
            raise ValueError(f"unsupported EC curve: {curve_name}")
        coord_len = (public_key.curve.key_size + 7) // 8
        numbers = public_key.public_numbers()
        jwk: dict[str, Any] = {
            "kty": "EC",
            "crv": crv,
            "x": _b64url_uint(numbers.x, coord_len),
            "y": _b64url_uint(numbers.y, coord_len),
            "use": "sig",
            "alg": algorithm,
        }
    elif isinstance(public_key, rsa.RSAPublicKey):
        numbers = public_key.public_numbers()
        modulus_len = (numbers.n.bit_length() + 7) // 8
        jwk = {
            "kty": "RSA",
            "n": _b64url_uint(numbers.n, modulus_len),
            "e": _b64url_uint(numbers.e),
            "use": "sig",
            "alg": algorithm,
        }
    else:
        raise ValueError(f"unsupported key type for JWKS: {type(public_key).__name__}")

    jwk["kid"] = _jwk_thumbprint(jwk)
    return {"keys": [jwk]}


def _b64url_uint(value: int, byte_length: int | None = None) -> str:
    if byte_length is None:
        byte_length = max(1, (value.bit_length() + 7) // 8)
    return base64.urlsafe_b64encode(value.to_bytes(byte_length, "big")).rstrip(b"=").decode()


def _jwk_thumbprint(jwk: dict[str, Any]) -> str:
    # RFC 7638 §3.2 — only the required members, sorted, no whitespace.
    if jwk["kty"] == "EC":
        members = {"crv": jwk["crv"], "kty": "EC", "x": jwk["x"], "y": jwk["y"]}
    elif jwk["kty"] == "RSA":
        members = {"e": jwk["e"], "kty": "RSA", "n": jwk["n"]}
    else:
        raise ValueError(f"thumbprint unsupported for kty={jwk['kty']}")
    canonical = json.dumps(members, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(hashlib.sha256(canonical).digest()).rstrip(b"=").decode()
