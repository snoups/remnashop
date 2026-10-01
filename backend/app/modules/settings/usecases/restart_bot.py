from loguru import logger
from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.constants import TELEGRAM_RESTART_CHANNEL
from app.core.security.permissions import Permission
from app.core.usecase import UseCase


class RestartBotUseCase(UseCase[None, None]):
    required_permission = Permission.BOT_RESTART

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def _execute(self, actor: Actor, data: None) -> None:
        # Fire-and-forget: if no telegram process is currently subscribed, this
        # is silently dropped -- its next start reads bot_settings fresh anyway.
        # The process doesn't hot-swap Bot/Dispatcher in place; it exits (SIGTERM)
        # and relies on the process supervisor (Docker's restart policy in prod)
        # to bring it back up with the new settings, matching how Remnawave
        # restarts an Xray node on config change rather than hot-reloading it.
        logger.info(f"Bot restart requested by actor {actor.log}")
        await self._redis.publish(TELEGRAM_RESTART_CHANNEL, "restart")
