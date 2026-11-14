from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import BotSignals, EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.dto import TranslationEntryDto
from app.modules.translations.events import TranslationChangedEvent
from app.modules.translations.ports import BotCommandsSync
from app.modules.translations.repository import TranslationRepository


class ResetAllTranslationsUseCase(UseCase[None, list[TranslationEntryDto]]):
    required_permission = Permission.TRANSLATIONS_RESET_ALL

    def __init__(
        self,
        translation_repository: TranslationRepository,
        uow: UnitOfWork,
        bot_commands: BotCommandsSync,
        bot_signals: BotSignals,
        event_publisher: EventPublisher,
    ) -> None:
        self._translation_repository = translation_repository
        self._uow = uow
        self._bot_commands = bot_commands
        self._bot_signals = bot_signals
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> list[TranslationEntryDto]:
        async with self._uow:
            locales = await self._translation_repository.list_active_locales()
            for locale in locales:
                await self._translation_repository.reset_locale(locale)
            reset = [
                entry
                for locale in locales
                for entry in await self._translation_repository.list_by_locale(locale)
            ]
            await self._event_publisher.publish(
                TranslationChangedEvent(actor=actor, action="reset_all")
            )

        # one full reload instead of a signal per key
        await self._bot_signals.dialogs_changed()

        await self._bot_commands.push()
        return reset
