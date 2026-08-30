from typing import Callable, Coroutine

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import HTTPException, Request, status
from loguru import logger
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX
from app.core.utils.http import resolve_client_ip


def rate_limit(
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> Callable[[Request, Redis], Coroutine[None, None, None]]:
    @inject
    async def dependency(request: Request, redis: FromDishka[Redis]) -> None:
        client_ip = resolve_client_ip(request)
        redis_key = f"{REDIS_KEY_PREFIX}ratelimit:{key}:{client_ip}"

        current = await redis.incr(redis_key)
        # NX (not "only on current == 1") so a crash/dropped connection between
        # incr() and expire() self-heals on the next request instead of leaving
        # the key stuck with no TTL forever.
        await redis.expire(redis_key, window_seconds, nx=True)

        if current > limit:
            logger.warning(f"Rate limit '{key}' exceeded by IP '{client_ip}'")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, try again later",
            )

    return dependency
