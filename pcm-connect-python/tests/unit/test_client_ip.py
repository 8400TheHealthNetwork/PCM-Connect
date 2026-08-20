from __future__ import annotations

from src.observability.client_ip import resolve_client_ip


def test_ignores_xff_when_no_proxy_is_trusted() -> None:
    assert (
        resolve_client_ip(
            peer_ip="10.0.0.4",
            x_forwarded_for="198.51.100.20",
            trusted_proxy_hops=0,
        )
        == "10.0.0.4"
    )


def test_selects_from_right_and_ignores_spoofed_leftmost_value() -> None:
    assert (
        resolve_client_ip(
            peer_ip="10.0.0.4",
            x_forwarded_for="192.0.2.250, 198.51.100.20",
            trusted_proxy_hops=1,
        )
        == "198.51.100.20"
    )


def test_supports_two_trusted_proxies() -> None:
    assert (
        resolve_client_ip(
            peer_ip="10.0.0.5",
            x_forwarded_for="192.0.2.250, 198.51.100.20, 10.0.0.4",
            trusted_proxy_hops=2,
        )
        == "198.51.100.20"
    )


def test_parses_aws_values_with_ports() -> None:
    assert (
        resolve_client_ip(
            peer_ip="10.0.0.4",
            x_forwarded_for="198.51.100.20:8443",
            trusted_proxy_hops=1,
        )
        == "198.51.100.20"
    )
    assert (
        resolve_client_ip(
            peer_ip="10.0.0.4",
            x_forwarded_for="[2001:db8::20]:8443",
            trusted_proxy_hops=1,
        )
        == "2001:db8::20"
    )


def test_falls_back_to_peer_for_invalid_or_short_chain() -> None:
    assert (
        resolve_client_ip(
            peer_ip="10.0.0.4",
            x_forwarded_for="not-an-ip",
            trusted_proxy_hops=1,
        )
        == "10.0.0.4"
    )
    assert (
        resolve_client_ip(
            peer_ip="10.0.0.4",
            x_forwarded_for="198.51.100.20",
            trusted_proxy_hops=2,
        )
        == "10.0.0.4"
    )
