from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings import SettingsRepository, repush_bot_commands_if_configured
from app.modules.translations.dto import TranslationsImportResultDto, TranslationTextExportDto
from app.modules.translations.publish import publish_translation_change
from app.modules.translations.repository import TranslationsRepository
from app.modules.translations.usecases.export_translations import EXPORT_VERSION


@dataclass(frozen=True, kw_only=True)
class TranslationsImportInput:
    version: int
    texts: list[TranslationTextExportDto]


class ImportTranslationsUseCase(UseCase[TranslationsImportInput, TranslationsImportResultDto]):
    required_permission = Permission.TRANSLATIONS_IMPORT

    def __init__(
        self,
        translations_repository: TranslationsRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        config: AppConfig,
        redis: Redis,
    ) -> None:
        self._translations_repository = translations_repository
        self._settings_repository = settings_repository
        self._uow = uow
        self._config = config
        self._redis = redis

    async def _execute(
        self, actor: Actor, data: TranslationsImportInput
    ) -> TranslationsImportResultDto:
        if data.version != EXPORT_VERSION:
            raise ValidationError(
                f"Unsupported export version {data.version}, expected {EXPORT_VERSION}",
                code=ErrorCode.DIALOG_EXPORT_VERSION_UNSUPPORTED,
            )

        applied: list[TranslationTextExportDto] = []
        skipped = 0
        async with self._uow:
            active = set(await self._settings_repository.list_active_locales())
            for text in data.texts:
                # A string the file has but this install doesn't -- a locale
                # that was switched off, or a key from an older catalog -- is
                # skipped rather than created: an unknown key would only ever
                # sit in the DB unread.
                if text.locale not in active:
                    skipped += 1
                    continue
                try:
                    await self._translations_repository.update_value(
                        text.locale, text.message_id, text.attribute_id, text.value
                    )
                except NotFoundError:
                    skipped += 1
                    continue
                applied.append(text)

        for text in applied:
            await publish_translation_change(
                self._redis,
                text.locale,
                text.message_id,
                text.value,
                attribute_id=text.attribute_id,
            )

        await repush_bot_commands_if_configured(
            self._settings_repository, self._translations_repository, self._config, self._uow
        )
        return TranslationsImportResultDto(applied=len(applied), skipped=skipped)
