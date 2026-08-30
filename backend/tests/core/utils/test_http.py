from typing import Optional

import pytest
from fastapi import Request

from app.core.exceptions import ValidationError
from app.core.utils.http import assert_public_https_host, is_ip_allowed, resolve_client_ip


def _make_request(client_host: Optional[str], headers: Optional[dict[str, str]] = None) -> Request:
    scope = {
        "type": "http",
        "client": (client_host, 12345) if client_host is not None else None,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    return Request(scope)


def test_is_ip_allowed_exact_match() -> None:
    assert is_ip_allowed("10.0.0.1", ["10.0.0.1"])


def test_is_ip_allowed_cidr_match() -> None:
    assert is_ip_allowed("192.168.1.42", ["192.168.1.0/24"])


def test_is_ip_allowed_rejects_outside_range() -> None:
    assert not is_ip_allowed("192.168.2.1", ["192.168.1.0/24"])


def test_is_ip_allowed_rejects_unparseable_client_ip() -> None:
    assert not is_ip_allowed("not-an-ip", ["10.0.0.1"])


def test_is_ip_allowed_ignores_malformed_allowlist_entries() -> None:
    assert is_ip_allowed("10.0.0.1", ["garbage", "10.0.0.1"])


def test_is_ip_allowed_empty_allowlist_denies() -> None:
    assert not is_ip_allowed("10.0.0.1", [])


def test_resolve_client_ip_honors_forwarded_for_from_loopback_peer() -> None:
    request = _make_request("127.0.0.1", {"x-forwarded-for": "203.0.113.5"})
    assert resolve_client_ip(request) == "203.0.113.5"


def test_resolve_client_ip_ignores_forwarded_for_from_non_loopback_peer() -> None:
    request = _make_request("198.51.100.9", {"x-forwarded-for": "203.0.113.5"})
    assert resolve_client_ip(request) == "198.51.100.9"


def test_resolve_client_ip_honors_forwarded_for_from_docker_bridge_peer() -> None:
    # e.g. the local dev compose's Vite dev-server container proxying to `api`
    # over the docker bridge network, rather than through loopback.
    request = _make_request("172.18.0.5", {"x-forwarded-for": "203.0.113.5"})
    assert resolve_client_ip(request) == "203.0.113.5"


def test_resolve_client_ip_uses_last_entry_when_proxy_appends() -> None:
    # nginx's $proxy_add_x_forwarded_for appends its own view of the peer to
    # whatever the client already sent -- a client can prepend an arbitrary
    # spoofed IP, but only the last (rightmost) entry was written by the
    # trusted proxy itself.
    request = _make_request("127.0.0.1", {"x-forwarded-for": "203.0.113.5, 198.51.100.20"})
    assert resolve_client_ip(request) == "198.51.100.20"


def test_resolve_client_ip_no_header_uses_client_host() -> None:
    request = _make_request("127.0.0.1")
    assert resolve_client_ip(request) == "127.0.0.1"


def test_resolve_client_ip_no_client_returns_unknown() -> None:
    request = _make_request(None)
    assert resolve_client_ip(request) == "unknown"


async def test_assert_public_https_host_rejects_non_https() -> None:
    with pytest.raises(ValidationError):
        await assert_public_https_host("http://example.com")


async def test_assert_public_https_host_rejects_hostless_url() -> None:
    with pytest.raises(ValidationError):
        await assert_public_https_host("https://")


async def test_assert_public_https_host_rejects_loopback() -> None:
    with pytest.raises(ValidationError):
        await assert_public_https_host("https://127.0.0.1/callback")


async def test_assert_public_https_host_rejects_private_range() -> None:
    with pytest.raises(ValidationError):
        await assert_public_https_host("https://10.0.0.5/metadata")


async def test_assert_public_https_host_rejects_unresolvable_host() -> None:
    with pytest.raises(ValidationError):
        await assert_public_https_host("https://this-host-does-not-exist.invalid/")
