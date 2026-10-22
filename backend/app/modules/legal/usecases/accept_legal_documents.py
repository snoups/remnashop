from loguru import logger

from app.core.db.uow import UnitOfWork
from app.modules.legal.dto import AcceptLegalDocumentsDto, PendingLegalDocumentsDto
from app.modules.legal.pending import pending_for_user
from app.modules.legal.recorder import LegalAcceptanceRecorder
from app.modules.legal.repository import LegalRepository
from app.modules.translations import TranslationRepository


class AcceptLegalDocumentsUseCase:
    def __init__(
        self,
        legal_repository: LegalRepository,
        translation_repository: TranslationRepository,
        legal_acceptance_recorder: LegalAcceptanceRecorder,
        uow: UnitOfWork,
    ) -> None:
        self._legal_repository = legal_repository
        self._translation_repository = translation_repository
        self._legal_acceptance_recorder = legal_acceptance_recorder
        self._uow = uow

    async def execute(self, data: AcceptLegalDocumentsDto) -> PendingLegalDocumentsDto:
        async with self._uow:
            pending = await pending_for_user(
                self._legal_repository,
                self._translation_repository,
                data.user,
                data.channel,
                data.locale,
            )
            # a revision saved after the screen was shown must be shown before it counts
            if sorted(data.revision_ids) != sorted(d.id for d in pending.documents):
                return pending
            if not pending.documents:
                return pending
            await self._legal_acceptance_recorder.record_revisions(
                user_id=data.user.id,
                channel=data.channel,
                revision_ids=data.revision_ids,
                ip_address=data.client_ip,
            )
        logger.info(f"{data.user.log} Accepted legal documents {data.revision_ids}")
        return PendingLegalDocumentsDto(documents=[], is_update=False)
