import asyncio
from typing import Final

from dishka import AsyncContainer, Scope
from loguru import logger
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX
from app.modules.overview import CheckSystemHealthUseCase

_INTERVAL_S: Final[int] = 60
_SLOT_KEY: Final[str] = f"{REDIS_KEY_PREFIX}system_health:slot"


async def watch_system_health(container: AsyncContainer, redis: Redis) -> None:
    # runs in api rather than worker so a stopped worker gets reported too;
    # the slot is held for the whole interval, so replicas and APP_WORKERS check once
    while True:
        try:
            if await redis.set(_SLOT_KEY, "1", nx=True, ex=_INTERVAL_S - 5):
                async with container(scope=Scope.REQUEST) as request_container:
                    use_case = await request_container.get(CheckSystemHealthUseCase)
                    await use_case.system()
        except Exception:
            logger.exception("System health check failed")
        await asyncio.sleep(_INTERVAL_S)
