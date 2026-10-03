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
        # Fire-and-forget: with no telegram process listening it's dropped, and
        # the next start reads bot_settings anyway. The process exits on SIGTERM
        # and the supervisor (Docker's restart policy) brings it back.
        logger.info(f"Bot restart requested by actor {actor.log}")
        await self._bot_signals.restart()
