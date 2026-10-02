from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import BotCommandsSync, BotSignals
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.repository import TranslationRepository


class ResetAllTranslationsUseCase(UseCase[None, None]):
    required_permission = Permission.TRANSLATIONS_RESET_ALL

    def __init__(
        self,
        translation_repository: TranslationRepository,
        uow: UnitOfWork,
        bot_commands: BotCommandsSync,
        bot_signals: BotSignals,
    ) -> None:
        self._translation_repository = translation_repository
        self._uow = uow
        self._bot_commands = bot_commands
        self._bot_signals = bot_signals

    async def _execute(self, actor: Actor, data: None) -> None:
        async with self._uow:
            locales = await self._translation_repository.list_active_locales()
            for locale in locales:
                await self._translation_repository.reset_locale(locale)
            reset = [
                entry
                for locale in locales
                for entry in await self._translation_repository.list_by_locale(locale)
            ]

        for entry in reset:
            await self._bot_signals.translation_changed(
                entry.locale, entry.message_id, entry.attribute_id, entry.value
            )

        await self._bot_commands.push()
