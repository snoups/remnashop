import asyncio
import ipaddress
import socket
from typing import Final, Union
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError

_TRUSTED_PROXY_NETWORKS: Final[list[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]] = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]


def _is_trusted_proxy(peer: str) -> bool:
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return any(address in network for network in _TRUSTED_PROXY_NETWORKS)


def resolve_client_ip(request: Request) -> str:
    # X-Forwarded-For is trusted only from a loopback or RFC1918 peer: every
    # compose file binds `api` to 127.0.0.1, so only a same-host reverse proxy
    # or a container on the docker bridge can reach it. Exposed publicly, the
    # header is ignored.
    #
    # The LAST entry: there's exactly one trusted hop, and whether it
    # overwrites or appends (nginx's `$proxy_add_x_forwarded_for`), its own
    # view of the peer lands last. Anything before it may be spoofed.
    #
    # getlist, not get: repeated header lines form one list, and a proxy that
    # adds a line instead of merging (HAProxy's `option forwardfor` without
    # `if-none`) would otherwise leave us reading the client's line.
    direct_peer = request.client.host if request.client else None
    if direct_peer is None or not _is_trusted_proxy(direct_peer):
        return direct_peer or "unknown"

    forwarded_for = request.headers.getlist("x-forwarded-for")
    if forwarded_for:
        candidate = ",".join(forwarded_for).split(",")[-1].strip()
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            # A trusted hop never writes a non-address here; fall back to the
            # peer rather than letting the value reach a rate-limit bucket key
            # or an allowlist comparison.
            pass
    return direct_peer or "unknown"


async def read_bounded_body(request: Request, limit: int) -> bytes:
    # Streams rather than trusting Content-Length: a chunked request carries no
    # such header, so a length check alone bounds nothing. Callers are the
    # unauthenticated webhook routes, which must not buffer an arbitrary body
    # before they get to verify a signature over it.
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE)

    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE)
        chunks.append(chunk)
    return b"".join(chunks)


async def assert_public_https_host(url: str) -> None:
    # SSRF guard for admin-configured URLs the server fetches (OIDC discovery):
    # rejects hosts resolving to private, loopback, link-local or reserved
    # addresses. Checked on save and again by the caller before each request;
    # DNS rebinding between that check and the connect stays open until the
    # resolved IP is pinned, acceptable while only admins set these URLs.
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValidationError(
            "URL must be an https:// URL with a host", code=ErrorCode.URL_NOT_HTTPS
        )

    loop = asyncio.get_running_loop()
    try:
        addrinfo = await loop.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as error:
        raise ValidationError(
            f"Could not resolve host: {parsed.hostname}", code=ErrorCode.URL_HOST_UNRESOLVABLE
        ) from error

    for *_rest, sockaddr in addrinfo:
        address = ipaddress.ip_address(sockaddr[0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise ValidationError(
                f"URL host resolves to a non-public address: {parsed.hostname}",
                code=ErrorCode.URL_HOST_NOT_PUBLIC,
            )


def is_ip_allowed(client_ip: str, allowlist: list[str]) -> bool:
    try:
        address = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for entry in allowlist:
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            continue
        if address in network:
            return True

    return False
