from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.events import changed_fields
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.legal.dto import LegalDocumentDto, UpdateLegalDocumentDto
from app.modules.legal.events import LegalDocumentChangedEvent
from app.modules.legal.repository import LegalRepository


class UpdateLegalDocumentUseCase(UseCase[UpdateLegalDocumentDto, LegalDocumentDto]):
    required_permission = Permission.LEGAL_DOCUMENTS_UPDATE

    def __init__(
        self,
        legal_repository: LegalRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._legal_repository = legal_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: UpdateLegalDocumentDto) -> LegalDocumentDto:
        async with self._uow:
            before = next(
                document
                for document in await self._legal_repository.list_documents()
                if document.kind == data.kind
            )
            after = await self._legal_repository.update_document(
                data.kind, show_in_bot=data.show_in_bot, show_in_cabinet=data.show_in_cabinet
            )
            await self._event_publisher.publish(
                LegalDocumentChangedEvent(
                    actor=actor,
                    action="update",
                    kind=data.kind,
                    changed=changed_fields(before, after, ("show_in_bot", "show_in_cabinet")),
                    ip_address=data.client_ip,
                )
            )
        logger.info(f"{actor.log} Updated legal document '{data.kind.value}'")
        return after
