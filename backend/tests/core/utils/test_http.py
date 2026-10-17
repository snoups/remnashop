from types import SimpleNamespace
from typing import Optional

import pytest
from fastapi import HTTPException, Request

from app.core.exceptions import ValidationError
from app.core.utils.http import (
    assert_public_https_host,
    ip_rate_bucket,
    is_ip_allowed,
    read_bounded_body,
    resolve_client_ip,
)


def _make_request(
    client_host: Optional[str],
    headers: Optional[dict[str, str]] = None,
    *,
    header_pairs: Optional[list[tuple[str, str]]] = None,
) -> Request:
    # header_pairs, not headers, when a test needs the same field name twice
    pairs = header_pairs if header_pairs is not None else list((headers or {}).items())
    scope = {
        "type": "http",
        "client": (client_host, 12345) if client_host is not None else None,
        "headers": [(k.lower().encode(), v.encode()) for k, v in pairs],
    }
    return Request(scope)


def _cabinet_request(peer: str, secret: Optional[str], headers: dict[str, str]) -> Request:
    app = SimpleNamespace(state=SimpleNamespace(cabinet_proxy_secret=secret))
    scope = {
        "type": "http",
        "client": (peer, 1234),
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "app": app,
    }
    return Request(scope)


def test_resolve_client_ip_trusts_cabinet_header_with_secret() -> None:
    request = _cabinet_request(
        "198.51.100.9",
        "s3cret",
        {"x-cabinet-client-ip": "203.0.113.77", "x-cabinet-proxy-secret": "s3cret"},
    )
    assert resolve_client_ip(request) == "203.0.113.77"


def test_resolve_client_ip_ignores_cabinet_header_with_wrong_secret() -> None:
    request = _cabinet_request(
        "198.51.100.9",
        "s3cret",
        {"x-cabinet-client-ip": "203.0.113.77", "x-cabinet-proxy-secret": "nope"},
    )
    assert resolve_client_ip(request) == "198.51.100.9"


def test_resolve_client_ip_ignores_cabinet_header_when_secret_unset() -> None:
    request = _cabinet_request(
        "198.51.100.9",
        None,
        {"x-cabinet-client-ip": "203.0.113.77", "x-cabinet-proxy-secret": ""},
    )
    assert resolve_client_ip(request) == "198.51.100.9"


def test_resolve_client_ip_rejects_non_address_in_cabinet_header() -> None:
    request = _cabinet_request(
        "198.51.100.9",
        "s3cret",
        {"x-cabinet-client-ip": "evil", "x-cabinet-proxy-secret": "s3cret"},
    )
    assert resolve_client_ip(request) == "198.51.100.9"


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
    # nginx's $proxy_add_x_forwarded_for appends to what the client sent, so
    # only the rightmost entry comes from the proxy
    request = _make_request("127.0.0.1", {"x-forwarded-for": "203.0.113.5, 198.51.100.20"})
    assert resolve_client_ip(request) == "198.51.100.20"


def test_resolve_client_ip_uses_last_of_repeated_field_lines() -> None:
    # HTTP treats repeated field lines as one comma-joined list. A proxy that
    # adds a line rather than merging (HAProxy's `option forwardfor` without
    # `if-none`) leaves the client's own line first, so reading only the first
    # line would hand the client the value that keys rate limits and the IP
    # allowlist.
    request = _make_request(
        "127.0.0.1",
        header_pairs=[
            ("x-forwarded-for", "203.0.113.5"),
            ("x-forwarded-for", "198.51.100.20"),
        ],
    )
    assert resolve_client_ip(request) == "198.51.100.20"


def test_resolve_client_ip_falls_back_when_forwarded_value_is_not_an_address() -> None:
    request = _make_request("127.0.0.1", {"x-forwarded-for": "not-an-ip"})
    assert resolve_client_ip(request) == "127.0.0.1"


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


def _streaming_request(chunks: list[bytes], content_length: Optional[str] = None) -> Request:
    headers = [(b"content-length", content_length.encode())] if content_length else []
    scope = {"type": "http", "client": ("127.0.0.1", 12345), "headers": headers}

    queued = [{"type": "http.request", "body": chunk, "more_body": True} for chunk in chunks]
    queued.append({"type": "http.request", "body": b"", "more_body": False})

    async def receive() -> dict:
        return queued.pop(0)

    return Request(scope, receive)


async def test_read_bounded_body_returns_body_under_limit() -> None:
    request = _streaming_request([b"abc", b"def"])
    assert await read_bounded_body(request, 16) == b"abcdef"


async def test_read_bounded_body_rejects_declared_oversize() -> None:
    request = _streaming_request([b"x"], content_length="9999")
    with pytest.raises(HTTPException) as error:
        await read_bounded_body(request, 16)
    assert error.value.status_code == 413


async def test_read_bounded_body_rejects_oversize_without_content_length() -> None:
    # a chunked request has no Content-Length; the running total caps it
    request = _streaming_request([b"x" * 10, b"x" * 10])
    with pytest.raises(HTTPException) as error:
        await read_bounded_body(request, 16)
    assert error.value.status_code == 413


@pytest.mark.parametrize(
    ("ip", "bucket"),
    [
        ("203.0.113.5", "203.0.113.5"),
        ("::ffff:203.0.113.5", "203.0.113.5"),
        ("2001:db8:1:2:aaaa::1", "2001:db8:1:2::/64"),
        ("2001:db8:1:2:bbbb::9", "2001:db8:1:2::/64"),
        ("garbage", "garbage"),
    ],
)
def test_ip_rate_bucket(ip: str, bucket: str) -> None:
    assert ip_rate_bucket(ip) == bucket


def test_ip_rate_bucket_separates_different_64s() -> None:
    assert ip_rate_bucket("2001:db8:1:2::1") != ip_rate_bucket("2001:db8:1:3::1")
