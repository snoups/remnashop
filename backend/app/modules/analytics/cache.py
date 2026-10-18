import dataclasses
import json
from collections.abc import Awaitable, Callable
from typing import Final, Optional, TypeVar

from loguru import logger
from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.constants import REDIS_KEY_PREFIX, TTL_5M

# reports read the whole payment history; minutes-old figures are fine for them
_TTL_S: Final[int] = TTL_5M

ReportT = TypeVar("ReportT", bound=BaseModel)


class AnalyticsCache:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get_or_compute(
        self,
        report: str,
        params: Optional[object],
        model: type[ReportT],
        compute: Callable[[], Awaitable[ReportT]],
    ) -> ReportT:
        key = f"{REDIS_KEY_PREFIX}analytics:{report}:{_params_key(params)}"
        try:
            cached = await self._redis.get(key)
        except RedisError as error:
            logger.warning(f"Analytics cache read failed, computing '{report}': {error}")
            cached = None
        if cached is not None:
            try:
                return model.model_validate_json(cached)
            except ValidationError as error:
                logger.warning(f"Analytics cache payload is stale, computing '{report}': {error}")
        result = await compute()
        try:
            await self._redis.set(key, result.model_dump_json(), ex=_TTL_S)
        except RedisError as error:
            logger.warning(f"Analytics cache write failed for '{report}': {error}")
        return result


def _params_key(params: Optional[object]) -> str:
    if params is None:
        return "-"
    assert dataclasses.is_dataclass(params) and not isinstance(params, type)
    return json.dumps(dataclasses.asdict(params), default=str, sort_keys=True)
