from __future__ import annotations

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.auth.jwks import build_jwks, load_signing_key_pem


def test_jwks_for_es256_exposes_public_components(es256_keypair) -> None:
    private_pem, _ = es256_keypair
    jwks = build_jwks(private_pem, "ES256")

    assert "keys" in jwks and len(jwks["keys"]) == 1
    key = jwks["keys"][0]
    assert key["kty"] == "EC"
    assert key["crv"] == "P-256"
    assert key["alg"] == "ES256"
    assert key["use"] == "sig"
    assert key["x"] and key["y"]
    assert "kid" in key and key["kid"]


def test_jwks_does_not_leak_private_components(es256_keypair) -> None:
    private_pem, _ = es256_keypair
    jwks = build_jwks(private_pem, "ES256")
    key = jwks["keys"][0]
    # JWK private members per RFC 7518: `d` (EC/RSA), `p`, `q`, `dp`, `dq`, `qi`.
    for forbidden in ("d", "p", "q", "dp", "dq", "qi"):
        assert forbidden not in key


def test_jwks_kid_is_deterministic(es256_keypair) -> None:
    private_pem, _ = es256_keypair
    a = build_jwks(private_pem, "ES256")["keys"][0]["kid"]
    b = build_jwks(private_pem, "ES256")["keys"][0]["kid"]
    assert a == b


def test_jwks_supports_rsa() -> None:
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    jwks = build_jwks(private_pem, "RS256")
    key = jwks["keys"][0]
    assert key["kty"] == "RSA"
    assert key["alg"] == "RS256"
    assert key["n"] and key["e"]
    for forbidden in ("d", "p", "q", "dp", "dq", "qi"):
        assert forbidden not in key


def test_load_signing_key_pem_accepts_blob_or_path(es256_keypair, tmp_path) -> None:
    private_pem, _ = es256_keypair
    assert load_signing_key_pem(private_pem) == private_pem

    p = tmp_path / "key.pem"
    p.write_text(private_pem)
    assert load_signing_key_pem(str(p)) == private_pem


def test_published_jwk_verifies_token_signed_with_private_key(es256_keypair) -> None:
    """End-to-end: sign a JWT with the private key, verify it using the
    public key reconstructed from the JWKS we publish."""
    private_pem, _ = es256_keypair
    jwks = build_jwks(private_pem, "ES256")
    jwk = jwks["keys"][0]

    token = jwt.encode({"hello": "world"}, private_pem, algorithm="ES256")
    public_key = jwt.algorithms.ECAlgorithm.from_jwk(jwk)
    decoded = jwt.decode(token, public_key, algorithms=["ES256"])
    assert decoded == {"hello": "world"}
