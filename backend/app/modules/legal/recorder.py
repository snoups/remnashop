from typing import Optional

from app.core.enums import LegalAcceptanceTrigger, LegalDocumentKind, Locale, PurchaseChannel
from app.modules.legal.dto import CreateLegalAcceptanceDto
from app.modules.legal.repository import LegalRepository
from app.modules.legal.visibility import visible_documents
from app.modules.translations import TranslationRepository


class LegalAcceptanceRecorder:
    def __init__(
        self, legal_repository: LegalRepository, translation_repository: TranslationRepository
    ) -> None:
        self._repo = legal_repository
        self._translations = translation_repository

    async def record(
        self,
        *,
        user_id: int,
        channel: PurchaseChannel,
        trigger: LegalAcceptanceTrigger,
        locale: Locale,
        kinds: frozenset[LegalDocumentKind],
        transaction_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        default_locale = await self._translations.get_default_locale()
        revisions = await visible_documents(
            self._repo,
            await self._repo.list_documents(),
            channel,
            locale,
            default_locale,
            await self._translations.list_active_locales(),
        )
        await self._repo.add_acceptances(
            [
                CreateLegalAcceptanceDto(
                    user_id=user_id,
                    revision_id=revision.id,
                    channel=channel,
                    trigger=trigger,
                    transaction_id=transaction_id,
                    ip_address=ip_address,
                )
                for revision in revisions
                if revision.kind in kinds
            ]
        )

    async def record_revisions(
        self,
        *,
        user_id: int,
        channel: PurchaseChannel,
        revision_ids: list[int],
        ip_address: Optional[str],
    ) -> None:
        await self._repo.add_acceptances(
            [
                CreateLegalAcceptanceDto(
                    user_id=user_id,
                    revision_id=revision_id,
                    channel=channel,
                    trigger=LegalAcceptanceTrigger.SIGN_UP,
                    transaction_id=None,
                    ip_address=ip_address,
                )
                for revision_id in revision_ids
            ]
        )

    async def has_signed_up(self, user_id: int, channel: PurchaseChannel) -> bool:
        return await self._repo.has_acceptance(user_id, channel, LegalAcceptanceTrigger.SIGN_UP)
