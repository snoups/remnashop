from typing import Final

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings import SettingsRepository
from app.modules.translations.dto import TranslationsExportDto, TranslationTextExportDto
from app.modules.translations.repository import TranslationsRepository
from app.modules.users import UserDto

EXPORT_VERSION: Final[int] = 1


class ExportTranslationsUseCase(UseCase[None, TranslationsExportDto]):
    required_permission = Permission.TRANSLATIONS_EXPORT

    def __init__(
        self,
        translations_repository: TranslationsRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
    ) -> None:
        self._translations_repository = translations_repository
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> TranslationsExportDto:
        async with self._uow:
            locales = await self._settings_repository.list_active_locales()
            texts = [
                TranslationTextExportDto(
                    locale=locale,
                    message_id=entry.message_id,
                    attribute_id=entry.attribute_id,
                    value=entry.value,
                )
                for locale in locales
                for entry in await self._translations_repository.list_by_locale(locale)
            ]
        return TranslationsExportDto(version=EXPORT_VERSION, texts=texts)
