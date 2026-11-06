import json
import re
from datetime import datetime
from typing import Final, Optional

import httpx
from loguru import logger
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.constants import REDIS_KEY_PREFIX, TTL_10M
from app.core.utils.time import datetime_now

_KEY_PREFIX: Final[str] = f"{REDIS_KEY_PREFIX}panel_write:"
# outlives the webhook freshness window: an older event is refused anyway
WRITE_MARK_TTL_S: Final[int] = TTL_10M
_WRITE_METHODS: Final[frozenset[str]] = frozenset({"POST", "PATCH", "DELETE"})
# /users/{id}, /users/{id}/actions/<verb>; PATCH /users carries the id in its body
_USER_PATH: Final[re.Pattern[str]] = re.compile(r"/users/(\d+)(?:/actions/[\w-]+)?$")


def _written_user_id(request: httpx.Request) -> Optional[int]:
    if request.method not in _WRITE_METHODS:
        return None
    path = request.url.path
    if match := _USER_PATH.search(path):
        return int(match.group(1))
    if request.method == "PATCH" and path.endswith("/users"):
        try:
            user_id = json.loads(request.content).get("id")
        except (ValueError, AttributeError):
            return None
        return user_id if isinstance(user_id, int) else None
    return None


async def written_after(redis: Redis, user_id: int, moment: datetime) -> bool:
    """Whether the shop wrote this panel user after `moment` (a webhook's timestamp)."""
    raw = await redis.get(f"{_KEY_PREFIX}{user_id}")
    return raw is not None and datetime.fromisoformat(raw) > moment


class PanelWriteRecorder(httpx.AsyncBaseTransport):
    """Notes when the shop changes a panel user, so a webhook the panel built
    before that change and delivered after it can't roll the subscription back.
    The time is taken before sending: the panel's own echo of this write is
    newer and still applies."""

    def __init__(self, wrapped: httpx.AsyncBaseTransport, redis: Redis) -> None:
        self._wrapped = wrapped
        self._redis = redis

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        user_id = _written_user_id(request)
        sent_at = datetime_now()
        response = await self._wrapped.handle_async_request(request)
        if user_id is not None and response.status_code < 400:
            # the write itself went through: a lost mark must not turn it into an error
            try:
                await self._redis.set(
                    f"{_KEY_PREFIX}{user_id}", sent_at.isoformat(), ex=WRITE_MARK_TTL_S
                )
            except RedisError:
                logger.exception(f"Failed to mark a write to panel user {user_id}")
        return response

    async def aclose(self) -> None:
        await self._wrapped.aclose()
