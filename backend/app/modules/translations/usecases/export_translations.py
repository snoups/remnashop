from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.dto import (
    EXPORT_VERSION,
    TranslationsExportDto,
    TranslationTextExportDto,
)
from app.modules.translations.repository import TranslationRepository


class ExportTranslationsUseCase(UseCase[None, TranslationsExportDto]):
    required_permission = Permission.TRANSLATIONS_EXPORT

    def __init__(
        self,
        translation_repository: TranslationRepository,
        uow: UnitOfWork,
    ) -> None:
        self._translation_repository = translation_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> TranslationsExportDto:
        async with self._uow:
            locales = await self._translation_repository.list_active_locales()
            texts = [
                TranslationTextExportDto(
                    locale=locale,
                    message_id=entry.message_id,
                    attribute_id=entry.attribute_id,
                    value=entry.value,
                )
                for locale in locales
                for entry in await self._translation_repository.list_by_locale(locale)
            ]
        return TranslationsExportDto(version=EXPORT_VERSION, texts=texts)
