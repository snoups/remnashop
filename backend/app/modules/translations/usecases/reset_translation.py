from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import BotCommandsSync, BotSignals
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.dto import ResetTranslationDto, TranslationEntryDto
from app.modules.translations.repository import TranslationRepository


class ResetTranslationUseCase(UseCase[ResetTranslationDto, TranslationEntryDto]):
    required_permission = Permission.TRANSLATIONS_RESET

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

    async def _execute(self, actor: Actor, data: ResetTranslationDto) -> TranslationEntryDto:
        async with self._uow:
            reset = await self._translation_repository.reset_value(
                data.locale, data.message_id, data.attribute_id
            )

        await self._bot_signals.translation_changed(
            data.locale, data.message_id, data.attribute_id, reset.value
        )

        await self._bot_commands.push()
        return reset
