"""Exercise PCM end-to-end with a self-contained chain.

Every run:
  1. Mint a fresh RS256 client_assertion JWT (signed with the bundle key).
  2. POST it to /token to obtain an access_token.
  3. POST another fresh client_assertion to /introspect, asking about that token.
  4. Print the introspection response.

You may optionally pass an opaque token as argv[1] to skip step 1-2 and only
introspect that specific token.

Required env vars (see .env.example):
    DS_ADAPTER_PCM_CLIENT_CERT   path to client cert
    DS_ADAPTER_PCM_CLIENT_KEY    path to client key (also used to sign assertion)
    DS_ADAPTER_PCM_CA_CERT       path to CA cert
    DS_ADAPTER_CLIENT_ID         clientId from bundle.json
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.auth.mtls import create_mtls_client
from src.auth.pcm_client import PCMClient
from src.config import load_config
from src.errors import DSAdapterError


async def main() -> int:
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
        client_assertion_audience=config.pcm.client_assertion_audience,
        token_scope=config.pcm.token_scope,
        introspect_auth_method=config.pcm.introspect_auth_method,
    )

    print(f"PCM:        {config.pcm.base_url}")
    print(f"client_id:  {client_id}")
    print(f"alg:        {config.pcm.client_assertion_algorithm}")
    print(f"scope:      {config.pcm.token_scope}")
    print(f"introspect: {config.pcm.introspect_auth_method}")
    print()

    try:
        if len(sys.argv) > 1:
            opaque = sys.argv[1]
            print(f"(using token from argv: {opaque[:24]}...)")
        else:
            print(f"-> POST {pcm.token_url}")
            opaque = await pcm.get_token()
            print(f"   ✓ access_token: {opaque}")
            print()

        print(f"-> POST {pcm.introspect_url}")
        try:
            result = await pcm.introspect(opaque)
        except DSAdapterError as exc:
            if exc.code in ("AUTH_002", "AUTH_003"):
                print(f"   PCM accepted our auth and reported the token as INVALID ({exc.code}).")
                print("   ✓ mTLS + RS256 client_assertion + introspect wiring all work.")
                print("   (Note: tokens minted via /token by the adapter itself are not")
                print("    introspection-active — only SP-issued patient-context tokens are.)")
                return 0
            print(f"   ✗ {exc.code}: {exc}", file=sys.stderr)
            return 1

        print("   ✓ active token. Response:")
        print(json.dumps(result.model_dump(exclude={"extras"}), indent=2))
        return 0
    except DSAdapterError as exc:
        print(f"\n✗ Failed at PCM hop: {exc.code} — {exc}", file=sys.stderr)
        return 1
    finally:
        await pcm_http.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
