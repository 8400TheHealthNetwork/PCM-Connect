"""Fetch an access token from PCM /token using mTLS + RS256 client_assertion.

The connectathon PCM requires an RFC 8707 'resource' parameter in the token
request. Pass it via --resource or DS_ADAPTER_PCM_TOKEN_RESOURCE env var.

Usage:
    python scripts/get_pcm_token.py [--resource <uri>]
    python scripts/get_pcm_token.py --resource https://connecthon-python.demo
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.auth.mtls import create_mtls_client
from src.auth.pcm_client import PCMClient
from src.config import load_config
from src.errors import DSAdapterError


async def main(resource: str | None) -> int:
    config = load_config(ROOT / "config.yaml")

    key_path = os.environ.get("DS_ADAPTER_PCM_CLIENT_KEY")
    if not key_path:
        print("ERROR: DS_ADAPTER_PCM_CLIENT_KEY not set", file=sys.stderr)
        return 2
    signing_key = Path(key_path).read_text(encoding="utf-8")
    client_id = os.environ.get("DS_ADAPTER_CLIENT_ID", "ds-adapter")

    pcm_http = create_mtls_client(config.pcm)
    pcm = PCMClient(
        http=pcm_http,
        base_url=config.pcm.base_url,
        token_endpoint=config.pcm.token_endpoint,
        introspect_endpoint=config.pcm.introspect_endpoint,
        client_id=client_id,
        client_signing_key=signing_key,
        client_assertion_algorithm=config.pcm.client_assertion_algorithm,
        introspect_auth_method=config.pcm.introspect_auth_method,
        token_resource=resource or config.pcm.token_resource,
    )

    print(f"PCM:        {config.pcm.base_url}")
    print(f"client_id:  {client_id}")
    print(f"alg:        {config.pcm.client_assertion_algorithm}")
    print(f"resource:   {resource or config.pcm.token_resource or '(none)'}")
    print()

    try:
        print(f"-> POST {pcm.token_url}")
        token = await pcm.get_token()
        print(f"   ✓ access_token ({len(token)} chars):")
        print(f"     {token}")
        return 0
    except DSAdapterError as exc:
        print(f"   ✗ {exc.code}: {exc}", file=sys.stderr)
        return 1
    finally:
        await pcm_http.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--resource", help="RFC 8707 resource indicator URI")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.resource)))
