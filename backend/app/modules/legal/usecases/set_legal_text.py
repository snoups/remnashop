from typing import Final

from loguru import logger

from app.core.actor import Actor, actor_user_id
from app.core.db.uow import UnitOfWork
from app.core.enums import LegalDocumentKind
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.legal.dto import CreateLegalRevisionDto, LegalRevisionDto, SetLegalTextDto
from app.modules.legal.events import LegalDocumentChangedEvent
from app.modules.legal.repository import LegalRepository
from app.modules.translations import TranslationRepository

MAX_MESSAGE_LENGTH: Final[int] = 32768
MAX_TITLE_LENGTH: Final[int] = 160


class SetLegalTextUseCase(UseCase[SetLegalTextDto, LegalRevisionDto]):
    required_permission = Permission.LEGAL_TEXT_SET

    def __init__(
        self,
        legal_repository: LegalRepository,
        translation_repository: TranslationRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._legal_repository = legal_repository
        self._translation_repository = translation_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: SetLegalTextDto) -> LegalRevisionDto:
        if data.requires_reacceptance and data.kind == LegalDocumentKind.OFFER:
            raise ValidationError(
                "The offer is accepted by paying",
                code=ErrorCode.LEGAL_REACCEPTANCE_NOT_ALLOWED,
            )
        if not data.title.strip() or not data.body.strip():
            raise ValidationError("Title and body are required", code=ErrorCode.LEGAL_TEXT_REQUIRED)
        if (
            len(data.title) > MAX_TITLE_LENGTH
            or len(f"# {data.title}\n\n{data.body}") > MAX_MESSAGE_LENGTH
        ):
            raise ValidationError("Legal text is too long", code=ErrorCode.LEGAL_TEXT_TOO_LONG)

        async with self._uow:
            if data.locale not in await self._translation_repository.list_active_locales():
                raise ValidationError(
                    f"Locale not enabled: {data.locale}", code=ErrorCode.LOCALE_NOT_ENABLED
                )
            revision = await self._legal_repository.add_revision(
                CreateLegalRevisionDto(
                    kind=data.kind,
                    locale=data.locale,
                    channel=data.channel,
                    title=data.title,
                    body=data.body,
                    created_by=actor_user_id(actor),
                    requires_reacceptance=data.requires_reacceptance,
                )
            )
            await self._event_publisher.publish(
                LegalDocumentChangedEvent(
                    actor=actor,
                    action="text_set",
                    kind=data.kind,
                    locale=data.locale,
                    channel=data.channel,
                    changed=(
                        ["title", "body", "requires_reacceptance"]
                        if data.requires_reacceptance
                        else ["title", "body"]
                    ),
                    ip_address=data.client_ip,
                )
            )
        logger.info(f"{actor.log} Set legal text '{data.kind.value}' '{data.locale.value}'")
        return revision
