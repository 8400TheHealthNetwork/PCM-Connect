from __future__ import annotations

import ipaddress


def _parse_ip(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None

    # AWS can include the client port. IPv6 is bracketed in that mode.
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    else:
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            if candidate.count(":") == 1:
                candidate = candidate.rsplit(":", 1)[0]

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def resolve_client_ip(
    *,
    peer_ip: str,
    x_forwarded_for: str | None,
    trusted_proxy_hops: int,
) -> str:
    """Resolve the client from the right side of a trusted proxy chain.

    `trusted_proxy_hops=0` ignores X-Forwarded-For. A value of one trusts the
    immediate proxy and selects the address immediately before it. This avoids
    accepting caller-controlled leftmost entries as authoritative.
    """

    if trusted_proxy_hops <= 0 or not x_forwarded_for:
        return peer_ip

    forwarded = [part.strip() for part in x_forwarded_for.split(",") if part.strip()]
    chain = [*forwarded, peer_ip]
    position = len(chain) - trusted_proxy_hops - 1
    if position < 0:
        return peer_ip

    resolved = _parse_ip(chain[position])
    return resolved or peer_ip
