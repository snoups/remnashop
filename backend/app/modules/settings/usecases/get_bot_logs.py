from typing import Awaitable, cast

from redis.asyncio import Redis

from app.core.constants import TELEGRAM_LOGS_KEY
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users import UserDto


class GetBotLogsUseCase(UseCase[None, list[str]]):
    required_permission = Permission.BOT_LOGS_VIEW

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def _execute(self, actor: UserDto, data: None) -> list[str]:
        # Written by the telegram process itself (app.core.logger.add_redis_sink).
        return await cast(Awaitable[list[str]], self._redis.lrange(TELEGRAM_LOGS_KEY, 0, -1))
