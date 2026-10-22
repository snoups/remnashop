from typing import Optional

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PurchaseChannel
from app.modules.legal.dto import LegalRevisionDto
from app.modules.legal.repository import LegalRepository
from app.modules.legal.visibility import visible_documents
from app.modules.translations import TranslationRepository


class ListVisibleLegalDocumentsUseCase:
    def __init__(
        self,
        legal_repository: LegalRepository,
        translation_repository: TranslationRepository,
        uow: UnitOfWork,
    ) -> None:
        self._legal_repository = legal_repository
        self._translation_repository = translation_repository
        self._uow = uow

    async def execute(
        self, channel: PurchaseChannel, locale: Optional[Locale]
    ) -> list[LegalRevisionDto]:
        async with self._uow:
            default_locale = await self._translation_repository.get_default_locale()
            return await visible_documents(
                self._legal_repository,
                await self._legal_repository.list_documents(),
                channel,
                locale,
                default_locale,
                await self._translation_repository.list_active_locales(),
            )
