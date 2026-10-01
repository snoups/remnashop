import asyncio
from typing import Final

import httpx

from app.core.enums import BlacklistKind
from app.core.utils.http import assert_public_https_host
from app.modules.blacklist.dto import ParsedSourceList
from app.modules.blacklist.normalize import normalize_identity

_TIMEOUT_S: Final[float] = 10.0
# httpx's timeout is per read, so a source trickling bytes never trips it;
# this bounds the whole download.
_DEADLINE_S: Final[float] = 60.0
_MAX_BYTES: Final[int] = 5 * 1024 * 1024


def parse_source_text(text: str) -> ParsedSourceList:
    ids: set[int] = set()
    emails: set[str] = set()
    for line in text.splitlines():
        token = line.split("#", 1)[0].strip()
        if not token:
            continue
        token = token.split()[0]
        # EMAIL first: normalize_identity(TELEGRAM_ID, ...) strips every
        # non-digit, so "john99@gmail.com" would otherwise become id 99.
        if "@" in token:
            email = normalize_identity(BlacklistKind.EMAIL, token)
            if email is not None:
                emails.add(email)
            continue
        tg = normalize_identity(BlacklistKind.TELEGRAM_ID, token)
        if tg is not None:
            ids.add(int(tg))
    return ParsedSourceList(telegram_ids=sorted(ids), emails=sorted(emails))


async def _download(url: str) -> bytes:
    # follow_redirects=False: assert_public_https_host only vets the initial
    # host, a followed redirect would land anywhere. Raw blocklist URLs serve
    # directly.
    async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=False) as client:
        async with client.stream("GET", url) as response:
            if response.is_redirect:
                raise ValueError(f"blacklist source redirects, which is not followed: {url}")
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > _MAX_BYTES:
                    raise ValueError(f"blacklist source body exceeds {_MAX_BYTES} bytes: {url}")
                chunks.append(chunk)
    return b"".join(chunks)


async def fetch_source(url: str) -> ParsedSourceList:
    await assert_public_https_host(url)
    try:
        async with asyncio.timeout(_DEADLINE_S):
            body = await _download(url)
    except TimeoutError as error:
        raise ValueError(
            f"blacklist source did not finish within {_DEADLINE_S:.0f}s: {url}"
        ) from error
    return parse_source_text(body.decode("utf-8", errors="replace"))
