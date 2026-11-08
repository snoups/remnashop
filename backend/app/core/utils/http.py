import asyncio
import hmac
import ipaddress
import re
import socket
from typing import Final, Optional, Union
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.core.constants import CABINET_CLIENT_IP_HEADER, CABINET_PROXY_SECRET_HEADER
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


def is_cabinet_proxied(request: Request) -> bool:
    """The request came through the cabinet's nginx: it carries that proxy's secret."""
    app = request.scope.get("app")
    expected = getattr(getattr(app, "state", None), "cabinet_proxy_secret", None)
    presented = request.headers.get(CABINET_PROXY_SECRET_HEADER)
    return bool(
        expected and presented and hmac.compare_digest(presented.encode(), expected.encode())
    )


def _cabinet_client_ip(request: Request) -> Optional[str]:
    # the cabinet's nginx overwrites both headers; the secret proves the hop is
    # that proxy, however many reverse proxies sit between it and us
    if not is_cabinet_proxied(request):
        return None
    try:
        return str(ipaddress.ip_address(request.headers.get(CABINET_CLIENT_IP_HEADER, "")))
    except ValueError:
        return None


def resolve_client_ip(request: Request) -> str:
    cabinet_ip = _cabinet_client_ip(request)
    if cabinet_ip is not None:
        return cabinet_ip

    # X-Forwarded-For only from a loopback or RFC1918 peer (compose binds `api` to
    # 127.0.0.1). The last entry is the one trusted hop's view of the peer,
    # anything before it may be spoofed. getlist: a proxy that adds a header line
    # instead of merging would otherwise leave us reading the client's line.
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


def ip_rate_bucket(ip: str) -> str:
    # an IPv6 user controls a whole /64, so per-address buckets are free to dodge
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def device_bucket(ip: str) -> str:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    prefix = 48 if isinstance(address, ipaddress.IPv6Address) else 16
    return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False))


_BROWSERS: Final[tuple[tuple[str, str], ...]] = (
    ("Telegram", r"Telegram"),
    ("Edge", r"Edg(?:e|A|iOS)?/"),
    ("Opera", r"OPR/"),
    ("Firefox", r"Firefox/|FxiOS/"),
    ("Chrome", r"Chrome/|CriOS/"),
    ("Safari", r"Version/[\d.]+.*Safari/"),
)
_SYSTEMS: Final[tuple[tuple[str, str], ...]] = (
    ("iOS", r"iPhone|iPad"),
    ("Android", r"Android"),
    ("Windows", r"Windows"),
    ("macOS", r"Macintosh|Mac OS X"),
    ("Linux", r"Linux|X11"),
)
_UNKNOWN_BROWSER: Final[str] = "Unknown browser"


def describe_user_agent(user_agent: Optional[str]) -> str:
    """Browser family and OS without versions, so an update keeps the same device."""
    agent = user_agent or ""
    browser = next((name for name, pattern in _BROWSERS if re.search(pattern, agent)), None)
    if browser is None:
        return _UNKNOWN_BROWSER
    system = next((name for name, pattern in _SYSTEMS if re.search(pattern, agent)), None)
    return browser if system is None else f"{browser} on {system}"


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


def validate_ip_allowlist(value: list[str]) -> list[str]:
    for entry in value:
        try:
            ipaddress.ip_network(entry, strict=False)
        except ValueError as error:
            raise ValueError(f"Invalid IP or CIDR: {entry}") from error
    return value


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
