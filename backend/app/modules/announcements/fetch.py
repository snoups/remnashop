from typing import Final

import httpx

from app.modules.announcements.feed import FEED_URL, FeedError

_TIMEOUT_S: Final[float] = 10.0
_MAX_BYTES: Final[int] = 1024 * 1024


async def fetch_feed(url: str = FEED_URL) -> bytes:
    # raw.githubusercontent serves directly; a redirect means something is off
    async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=False) as client:
        response = await client.get(url)
    response.raise_for_status()
    if len(response.content) > _MAX_BYTES:
        raise FeedError(f"announcements feed exceeds {_MAX_BYTES} bytes")
    return response.content
