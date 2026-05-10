from __future__ import annotations

import os
import ssl

import httpx

from src.config.models import PCMConfig


def create_mtls_client(pcm: PCMConfig, *, timeout: float = 10.0) -> httpx.AsyncClient:
    """Build an httpx AsyncClient honoring pcm.mtls_client.

    When mTLS is enabled, certificate / key / CA paths come from env vars per
    spec §4.3. Their values are file paths (mounted into the container).

    When pcm.verify_hostname is False, the chain is still verified against the
    CA but the SAN/hostname check is skipped — needed for connectathon servers
    whose cert names a fixed CN (e.g. "pcm-core") rather than the ELB host.
    """
    if not pcm.mtls_client:
        return httpx.AsyncClient(timeout=timeout)

    cert_path = os.environ.get("DS_ADAPTER_PCM_CLIENT_CERT")
    key_path = os.environ.get("DS_ADAPTER_PCM_CLIENT_KEY")
    ca_path = os.environ.get("DS_ADAPTER_PCM_CA_CERT")

    cert: tuple[str, str] | str | None
    if cert_path and key_path:
        cert = (cert_path, key_path)
    elif cert_path:
        cert = cert_path
    else:
        cert = None

    if pcm.verify_hostname:
        verify: ssl.SSLContext | str | bool = ca_path if ca_path else True
    else:
        ctx = ssl.create_default_context(cafile=ca_path) if ca_path else ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
        verify = ctx

    return httpx.AsyncClient(cert=cert, verify=verify, timeout=timeout)
