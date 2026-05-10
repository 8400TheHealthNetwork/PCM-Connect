from __future__ import annotations

from fastapi import Request

from src.errors import DSAdapterError


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


def get_bearer_token(request: Request) -> str:
    header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not header:
        raise DSAdapterError("missing Authorization header", code="AUTH_001")
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise DSAdapterError("malformed Authorization header", code="AUTH_001")
    return parts[1].strip()
