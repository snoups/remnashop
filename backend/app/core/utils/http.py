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
    # Only trust X-Forwarded-For when the direct TCP peer is loopback or on
    # an RFC1918 private range -- matches every docker-compose topology in
    # this project, where `api` is bound to 127.0.0.1 only and never to a
    # public interface, so the only things that can ever reach it directly
    # are a reverse proxy on the same host (loopback) or another container
    # on the same docker bridge network (private range, e.g. the local dev
    # compose's Vite proxy). If `api` is ever exposed directly to a public
    # interface, X-Forwarded-For is ignored rather than trusted.
    #
    # Takes the LAST entry, not the first: this project has exactly one
    # trusted hop (that reverse proxy). Whether it's configured to overwrite
    # the header or append to it (nginx's `$proxy_add_x_forwarded_for`), the
    # value it itself appends -- its own view of the real peer -- always
    # lands last. A client can prepend arbitrary spoofed entries either way;
    # only the rightmost one was written by something we trust.
    #
    # getlist, not get: repeated field lines are one comma-joined list per
    # HTTP field-order semantics, and a proxy that adds a line rather than
    # merging (HAProxy's `option forwardfor` without `if-none`) would
    # otherwise leave the client's own line as the one we read.
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
    # SSRF guard for admin-configured URLs the server itself later fetches
    # (OIDC issuer discovery). Resolves the hostname and rejects anything
    # pointing at a private/loopback/link-local/reserved address, so an
    # admin-level account can't repoint a server-side request at internal
    # infrastructure. checked once here (write-time) and again
    # immediately before each request (call-site's responsibility) -- still
    # leaves a DNS-rebinding TOCTOU window between that second check and the
    # actual connect; closing it fully needs pinning the resolved IP through
    # the request, not just re-checking, upgrade if this URL class ever
    # becomes untrusted-user-configurable rather than admin-only.
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
