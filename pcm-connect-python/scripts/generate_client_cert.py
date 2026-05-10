"""Generate an RSA 2048 client cert + key for registering with PCM.

Outputs three files under certs/generated-<id>/:
  - client.key  RSA 2048 private key, PEM (PKCS#8)
  - client.crt  Self-signed X.509 certificate, PEM
  - info.json   Metadata: clientId, thumbprint (SHA-256 of DER, base64url)

Usage:
    python scripts/generate_client_cert.py [client-id]

If client-id is omitted, a random URI like 'https://<hex>.demo' is generated.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import json
import sys
import uuid
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parent.parent


def generate(client_id: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IL"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "DS-Adapter-Demo"),
            x509.NameAttribute(NameOID.COMMON_NAME, client_id),
        ]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    key_path = out_dir / "client.key"
    cert_path = out_dir / "client.crt"
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    cert_der = cert.public_bytes(serialization.Encoding.DER)
    thumbprint = base64.urlsafe_b64encode(hashlib.sha256(cert_der).digest()).rstrip(b"=").decode()

    info = {
        "client_id": client_id,
        "thumbprint": thumbprint,
        "cert_path": str(cert_path.relative_to(ROOT)),
        "key_path": str(key_path.relative_to(ROOT)),
        "valid_from": cert.not_valid_before_utc.isoformat(),
        "valid_until": cert.not_valid_after_utc.isoformat(),
    }
    (out_dir / "info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


def main() -> int:
    client_id = sys.argv[1] if len(sys.argv) > 1 else f"https://{uuid.uuid4().hex[:12]}.demo"
    out_dir = ROOT / "certs" / f"generated-{uuid.uuid4().hex[:8]}"

    info = generate(client_id, out_dir)

    print(f"Generated → {out_dir.relative_to(ROOT)}/")
    print(json.dumps(info, indent=2))
    print()
    print("Next steps:")
    print(f"  1. Upload {info['cert_path']} to PCM (org admin UI / API).")
    print(f"  2. PCM will register a data source with this client_id and thumbprint.")
    print("  3. Point .env at the new credentials:")
    print(f"     DS_ADAPTER_PCM_CLIENT_CERT={info['cert_path']}")
    print(f"     DS_ADAPTER_PCM_CLIENT_KEY={info['key_path']}")
    print(f"     DS_ADAPTER_CLIENT_ID={client_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
