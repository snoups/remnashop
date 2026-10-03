from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import BotCommandsSync, BotSignals
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.dto import (
    TranslationsImportDto,
    TranslationsImportResultDto,
    TranslationTextExportDto,
)
from app.modules.translations.repository import TranslationRepository
from app.modules.translations.usecases.export_translations import EXPORT_VERSION


class ImportTranslationsUseCase(UseCase[TranslationsImportDto, TranslationsImportResultDto]):
    required_permission = Permission.TRANSLATIONS_IMPORT

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

    async def _execute(
        self, actor: Actor, data: TranslationsImportDto
    ) -> TranslationsImportResultDto:
        if data.version != EXPORT_VERSION:
            raise ValidationError(
                f"Unsupported export version {data.version}, expected {EXPORT_VERSION}",
                code=ErrorCode.DIALOG_EXPORT_VERSION_UNSUPPORTED,
            )

        applied: list[TranslationTextExportDto] = []
        skipped = 0
        async with self._uow:
            active = set(await self._translation_repository.list_active_locales())
            for text in data.texts:
                # a string this install doesn't have (a disabled locale, a key
                # from an older catalog) is skipped; nothing would ever read it
                if text.locale not in active:
                    skipped += 1
                    continue
                try:
                    await self._translation_repository.update_value(
                        text.locale, text.message_id, text.attribute_id, text.value
                    )
                except NotFoundError:
                    skipped += 1
                    continue
                applied.append(text)

        for text in applied:
            await self._bot_signals.translation_changed(
                text.locale, text.message_id, text.attribute_id, text.value
            )

        await self._bot_commands.push()
        return TranslationsImportResultDto(applied=len(applied), skipped=skipped)
