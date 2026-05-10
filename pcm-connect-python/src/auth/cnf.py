from __future__ import annotations

import base64
import hashlib

import structlog

log = structlog.get_logger()


def warn_if_cnf_mismatch(cnf: dict | None, peer_cert_der: bytes | None) -> None:
    """If both binding and client cert are present, compare hashes and log
    WARNING on mismatch. Per spec §5.1 step 7, this is non-blocking.
    """
    if not cnf or not peer_cert_der:
        return
    expected = cnf.get("x5t#S256")
    if not expected:
        return
    digest = hashlib.sha256(peer_cert_der).digest()
    actual = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    if actual != expected:
        log.warning("cnf_mismatch", expected=expected, actual=actual)
