from loguru import logger

from app.core.actor import Actor, actor_user_id
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.legal.dto import CreateLegalRevisionDto, LegalTextKeyDto
from app.modules.legal.events import LegalDocumentChangedEvent
from app.modules.legal.repository import LegalRepository


class RemoveLegalTextUseCase(UseCase[LegalTextKeyDto, None]):
    required_permission = Permission.LEGAL_TEXT_REMOVE

    def __init__(
        self,
        legal_repository: LegalRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._legal_repository = legal_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: LegalTextKeyDto) -> None:
        async with self._uow:
            current = next(
                (
                    text
                    for text in await self._legal_repository.list_current_revisions()
                    if (text.kind, text.locale, text.channel)
                    == (data.kind, data.locale, data.channel)
                    and text.body.strip()
                ),
                None,
            )
            if current is None:
                raise NotFoundError("Legal text not found", code=ErrorCode.NOT_FOUND)
            await self._legal_repository.add_revision(
                CreateLegalRevisionDto(
                    kind=data.kind,
                    locale=data.locale,
                    channel=data.channel,
                    title=current.title,
                    body="",
                    created_by=actor_user_id(actor),
                )
            )
            await self._event_publisher.publish(
                LegalDocumentChangedEvent(
                    actor=actor,
                    action="text_remove",
                    kind=data.kind,
                    locale=data.locale,
                    channel=data.channel,
                    changed=["body"],
                    ip_address=data.client_ip,
                )
            )
        logger.info(f"{actor.log} Removed legal text '{data.kind.value}' '{data.locale.value}'")
