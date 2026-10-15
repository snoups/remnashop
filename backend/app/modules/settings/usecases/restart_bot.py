from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import BotSignals, EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.events import BotSettingsChangedEvent


class RestartBotUseCase(UseCase[None, None]):
    required_permission = Permission.BOT_RESTART

    def __init__(
        self, bot_signals: BotSignals, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._bot_signals = bot_signals
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> None:
        # Fire-and-forget: with no telegram process listening it's dropped, and
        # the next start reads bot_settings anyway. The process exits on SIGTERM
        # and the supervisor (Docker's restart policy) brings it back.
        async with self._uow:
            await self._event_publisher.publish(
                BotSettingsChangedEvent(actor=actor, action="restart")
            )
        logger.info(f"{actor.log} Requested a bot restart")
        await self._bot_signals.restart()
