from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.legal.dto import LegalDocumentsDto
from app.modules.legal.repository import LegalRepository
from app.modules.legal.templates import LEGAL_TEMPLATES
from app.modules.translations import TranslationRepository


class ListLegalDocumentsUseCase(UseCase[None, LegalDocumentsDto]):
    required_permission = Permission.LEGAL_DOCUMENTS_VIEW

    def __init__(
        self,
        legal_repository: LegalRepository,
        translation_repository: TranslationRepository,
        uow: UnitOfWork,
    ) -> None:
        self._legal_repository = legal_repository
        self._translation_repository = translation_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> LegalDocumentsDto:
        async with self._uow:
            documents = await self._legal_repository.list_documents()
            requests = await self._legal_repository.list_reacceptance_requests()
            texts = [
                text.model_copy(
                    update={
                        "last_reacceptance_at": requests.get((text.kind, text.locale, text.channel))
                    }
                )
                for text in await self._legal_repository.list_current_revisions()
                if text.body.strip()
            ]
            locales = await self._translation_repository.list_active_locales()
        return LegalDocumentsDto(
            documents=documents,
            texts=texts,
            templates=[template for template in LEGAL_TEMPLATES if template.locale in locales],
            locales=locales,
        )
