from loguru import logger

from app.core.actor import Actor
from app.core.ports import BotSignals
from app.core.security.permissions import Permission
from app.core.usecase import UseCase


class RestartBotUseCase(UseCase[None, None]):
    required_permission = Permission.BOT_RESTART

    def __init__(self, bot_signals: BotSignals) -> None:
        self._bot_signals = bot_signals

    async def _execute(self, actor: Actor, data: None) -> None:
        # Fire-and-forget: if no telegram process is currently subscribed, this
        # is silently dropped -- its next start reads bot_settings fresh anyway.
        # The process doesn't hot-swap Bot/Dispatcher in place; it exits (SIGTERM)
        # and relies on the process supervisor (Docker's restart policy in prod)
        # to bring it back up with the new settings.
        logger.info(f"Bot restart requested by actor {actor.log}")
        await self._bot_signals.restart()
