from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.legal_document import (
    LegalAcceptance,
    LegalDocument,
    LegalDocumentRevision,
)
from app.core.enums import LegalAcceptanceTrigger, LegalDocumentKind, Locale, PurchaseChannel
from app.modules.legal.dto import (
    CreateLegalAcceptanceDto,
    CreateLegalRevisionDto,
    LegalAcceptanceDto,
    LegalDocumentDto,
    LegalRevisionDto,
)


class LegalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: LegalDocument) -> LegalDocumentDto:
        return LegalDocumentDto.model_validate(row, from_attributes=True)

    def _to_revision_dto(self, row: LegalDocumentRevision) -> LegalRevisionDto:
        return LegalRevisionDto.model_validate(row, from_attributes=True)

    def _to_acceptance_dto(
        self, row: LegalAcceptance, revision: LegalDocumentRevision
    ) -> LegalAcceptanceDto:
        return LegalAcceptanceDto(
            id=row.id,
            user_id=row.user_id,
            revision=self._to_revision_dto(revision),
            channel=row.channel,
            trigger=row.trigger,
            transaction_id=row.transaction_id,
            ip_address=row.ip_address,
            accepted_at=row.accepted_at,
        )

    async def _ensure_documents(self) -> dict[LegalDocumentKind, LegalDocument]:
        result = await self.session.execute(select(LegalDocument))
        rows = {row.kind: row for row in result.scalars()}
        for kind in LegalDocumentKind:
            if kind not in rows:
                rows[kind] = LegalDocument(kind=kind)
                self.session.add(rows[kind])
        await self.session.flush()
        return rows

    async def list_documents(self) -> list[LegalDocumentDto]:
        rows = await self._ensure_documents()
        return [self._to_dto(rows[kind]) for kind in LegalDocumentKind]

    async def update_document(
        self,
        kind: LegalDocumentKind,
        *,
        show_in_bot: Optional[bool],
        show_in_cabinet: Optional[bool],
    ) -> LegalDocumentDto:
        row = (await self._ensure_documents())[kind]
        if show_in_bot is not None:
            row.show_in_bot = show_in_bot
        if show_in_cabinet is not None:
            row.show_in_cabinet = show_in_cabinet
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def add_revision(self, data: CreateLegalRevisionDto) -> LegalRevisionDto:
        row = LegalDocumentRevision(
            kind=data.kind,
            locale=data.locale,
            channel=data.channel,
            title=data.title,
            body=data.body,
            created_by=data.created_by,
            requires_reacceptance=data.requires_reacceptance,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_revision_dto(row)

    async def list_current_revisions(self) -> list[LegalRevisionDto]:
        result = await self.session.execute(
            select(LegalDocumentRevision)
            .distinct(
                LegalDocumentRevision.kind,
                LegalDocumentRevision.locale,
                LegalDocumentRevision.channel,
            )
            .order_by(
                LegalDocumentRevision.kind,
                LegalDocumentRevision.locale,
                LegalDocumentRevision.channel,
                LegalDocumentRevision.id.desc(),
            )
        )
        return [self._to_revision_dto(row) for row in result.scalars()]

    async def _find_current(
        self, kind: LegalDocumentKind, locale: Locale, channel: Optional[PurchaseChannel]
    ) -> Optional[LegalDocumentRevision]:
        result = await self.session.execute(
            select(LegalDocumentRevision)
            .where(
                LegalDocumentRevision.kind == kind,
                LegalDocumentRevision.locale == locale,
                LegalDocumentRevision.channel.is_(None)
                if channel is None
                else LegalDocumentRevision.channel == channel,
            )
            .order_by(LegalDocumentRevision.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def resolve(
        self,
        kind: LegalDocumentKind,
        channel: PurchaseChannel,
        locale: Locale,
        default_locale: Locale,
    ) -> Optional[LegalRevisionDto]:
        chain: list[tuple[Locale, Optional[PurchaseChannel]]] = [
            (locale, channel),
            (locale, None),
            (default_locale, channel),
            (default_locale, None),
        ]
        for chain_locale, chain_channel in dict.fromkeys(chain):
            row = await self._find_current(kind, chain_locale, chain_channel)
            if row is not None and row.body.strip():
                return self._to_revision_dto(row)
        return None

    async def documents_version(self) -> str:
        # changes with every saved text and every visibility switch
        row = (
            await self.session.execute(
                select(
                    select(func.max(LegalDocumentRevision.id)).scalar_subquery(),
                    select(func.max(LegalDocument.updated_at)).scalar_subquery(),
                )
            )
        ).one()
        revision_id, updated_at = row
        return f"{revision_id or 0}:{updated_at.timestamp() if updated_at else 0}"

    async def latest_reacceptance_at(
        self, kind: LegalDocumentKind, locale: Locale, channel: Optional[PurchaseChannel]
    ) -> Optional[datetime]:
        channel_filter = (
            LegalDocumentRevision.channel.is_(None)
            if channel is None
            else or_(
                LegalDocumentRevision.channel.is_(None), LegalDocumentRevision.channel == channel
            )
        )
        latest: Optional[datetime] = await self.session.scalar(
            select(func.max(LegalDocumentRevision.created_at)).where(
                LegalDocumentRevision.kind == kind,
                LegalDocumentRevision.locale == locale,
                LegalDocumentRevision.requires_reacceptance.is_(True),
                channel_filter,
            )
        )
        return latest

    async def list_reacceptance_requests(
        self,
    ) -> dict[tuple[LegalDocumentKind, Locale, Optional[PurchaseChannel]], datetime]:
        result = await self.session.execute(
            select(
                LegalDocumentRevision.kind,
                LegalDocumentRevision.locale,
                LegalDocumentRevision.channel,
                func.max(LegalDocumentRevision.created_at),
            )
            .where(LegalDocumentRevision.requires_reacceptance.is_(True))
            .group_by(
                LegalDocumentRevision.kind,
                LegalDocumentRevision.locale,
                LegalDocumentRevision.channel,
            )
        )
        return {(kind, locale, channel): at for kind, locale, channel, at in result.all()}

    async def last_accepted_at(
        self, user_id: int, kind: LegalDocumentKind, channel: PurchaseChannel
    ) -> Optional[datetime]:
        accepted: Optional[datetime] = await self.session.scalar(
            select(func.max(LegalAcceptance.accepted_at))
            .join(LegalDocumentRevision, LegalDocumentRevision.id == LegalAcceptance.revision_id)
            .where(
                LegalAcceptance.user_id == user_id,
                LegalAcceptance.channel == channel,
                LegalDocumentRevision.kind == kind,
            )
        )
        return accepted

    async def add_acceptances(self, rows: list[CreateLegalAcceptanceDto]) -> None:
        self.session.add_all(
            LegalAcceptance(
                user_id=item.user_id,
                revision_id=item.revision_id,
                channel=item.channel,
                trigger=item.trigger,
                transaction_id=item.transaction_id,
                ip_address=item.ip_address,
            )
            for item in rows
        )
        await self.session.flush()

    async def has_acceptance(
        self, user_id: int, channel: PurchaseChannel, trigger: LegalAcceptanceTrigger
    ) -> bool:
        found = await self.session.scalar(
            select(LegalAcceptance.id)
            .where(
                LegalAcceptance.user_id == user_id,
                LegalAcceptance.channel == channel,
                LegalAcceptance.trigger == trigger,
            )
            .limit(1)
        )
        return found is not None

    async def list_acceptances(self, user_id: int) -> list[LegalAcceptanceDto]:
        result = await self.session.execute(
            select(LegalAcceptance, LegalDocumentRevision)
            .join(LegalDocumentRevision, LegalDocumentRevision.id == LegalAcceptance.revision_id)
            .where(LegalAcceptance.user_id == user_id)
            .order_by(LegalAcceptance.id.desc())
        )
        return [self._to_acceptance_dto(acc, rev) for acc, rev in result.all()]
