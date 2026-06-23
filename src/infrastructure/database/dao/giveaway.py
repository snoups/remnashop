from datetime import datetime
from typing import Optional, cast
from uuid import UUID

from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.common.dao import GiveawayDao
from src.application.dto import GiveawayCampaignDto, GiveawayEntryDto
from src.core.enums import GiveawayCampaignStatus, GiveawayEntryStatus, PurchaseType
from src.infrastructure.database.models import GiveawayCampaign, GiveawayEntry


class GiveawayDaoImpl(GiveawayDao):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _campaign_dto(model: GiveawayCampaign) -> GiveawayCampaignDto:
        return GiveawayCampaignDto(
            id=model.id,
            name=model.name,
            status=model.status,
            starts_at=model.starts_at,
            ends_at=model.ends_at,
            winner_count=model.winner_count,
            prize_amount=model.prize_amount,
            eligible_plan_id=model.eligible_plan_id,
            eligible_duration_days=model.eligible_duration_days,
            eligible_purchase_types=[
                PurchaseType(value) for value in model.eligible_purchase_types
            ],
            code_prefix=model.code_prefix,
            rules_text=model.rules_text,
            completed_at=model.completed_at,
            archived_at=model.archived_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _entry_dto(model: GiveawayEntry) -> GiveawayEntryDto:
        return GiveawayEntryDto(
            id=model.id,
            campaign_id=model.campaign_id,
            user_telegram_id=model.user_telegram_id,
            telegram_username=model.telegram_username,
            participant_code=model.participant_code,
            transaction_payment_id=model.transaction_payment_id,
            plan_id=model.plan_id,
            plan_name=model.plan_name,
            duration_days=model.duration_days,
            purchase_type=model.purchase_type,
            entry_source=model.entry_source,
            phone=model.phone,
            status=model.status,
            winner_rank=model.winner_rank,
            selected_at=model.selected_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def create_campaign(self, campaign: GiveawayCampaignDto) -> GiveawayCampaignDto:
        model = GiveawayCampaign(
            name=campaign.name,
            status=campaign.status,
            starts_at=campaign.starts_at,
            ends_at=campaign.ends_at,
            winner_count=campaign.winner_count,
            prize_amount=campaign.prize_amount,
            eligible_plan_id=campaign.eligible_plan_id,
            eligible_duration_days=campaign.eligible_duration_days,
            eligible_purchase_types=[item.value for item in campaign.eligible_purchase_types],
            code_prefix=campaign.code_prefix,
            rules_text=campaign.rules_text,
            completed_at=campaign.completed_at,
            archived_at=campaign.archived_at,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._campaign_dto(model)

    async def get_campaign(self, campaign_id: int) -> Optional[GiveawayCampaignDto]:
        model = await self.session.scalar(
            select(GiveawayCampaign).where(GiveawayCampaign.id == campaign_id)
        )
        return self._campaign_dto(model) if model else None

    async def get_campaigns(self) -> list[GiveawayCampaignDto]:
        result = await self.session.scalars(
            select(GiveawayCampaign).order_by(GiveawayCampaign.created_at.desc())
        )
        return [self._campaign_dto(item) for item in cast(list[GiveawayCampaign], result.all())]

    async def get_client_campaigns(
        self,
        now: datetime,
        user_telegram_id: int,
    ) -> list[GiveawayCampaignDto]:
        has_entry = exists(
            select(GiveawayEntry.id).where(
                GiveawayEntry.campaign_id == GiveawayCampaign.id,
                GiveawayEntry.user_telegram_id == user_telegram_id,
            )
        )
        result = await self.session.scalars(
            select(GiveawayCampaign)
            .where(
                or_(
                    and_(
                        GiveawayCampaign.status == GiveawayCampaignStatus.ACTIVE,
                        GiveawayCampaign.starts_at <= now,
                        GiveawayCampaign.ends_at >= now,
                    ),
                    and_(
                        GiveawayCampaign.status == GiveawayCampaignStatus.COMPLETED,
                        has_entry,
                    ),
                )
            )
            .order_by(GiveawayCampaign.ends_at.desc())
        )
        return [self._campaign_dto(item) for item in cast(list[GiveawayCampaign], result.all())]

    async def get_matching_campaigns(
        self,
        now: datetime,
        plan_id: int,
        duration_days: int,
        purchase_type: PurchaseType,
    ) -> list[GiveawayCampaignDto]:
        stmt = select(GiveawayCampaign).where(
            GiveawayCampaign.status == GiveawayCampaignStatus.ACTIVE,
            GiveawayCampaign.starts_at <= now,
            GiveawayCampaign.ends_at >= now,
            GiveawayCampaign.eligible_plan_id == plan_id,
            GiveawayCampaign.eligible_duration_days == duration_days,
            GiveawayCampaign.eligible_purchase_types.contains([purchase_type.value]),
        )
        result = await self.session.scalars(stmt)
        return [self._campaign_dto(item) for item in cast(list[GiveawayCampaign], result.all())]

    async def set_campaign_status(
        self,
        campaign_id: int,
        status: GiveawayCampaignStatus,
        now: datetime,
    ) -> Optional[GiveawayCampaignDto]:
        values: dict = {"status": status}
        if status == GiveawayCampaignStatus.COMPLETED:
            values["completed_at"] = now
        model = await self.session.scalar(
            update(GiveawayCampaign)
            .where(GiveawayCampaign.id == campaign_id)
            .values(**values)
            .returning(GiveawayCampaign)
        )
        if model:
            await self.session.refresh(model)
        return self._campaign_dto(model) if model else None

    async def archive_campaign(
        self,
        campaign_id: int,
        now: datetime,
    ) -> Optional[GiveawayCampaignDto]:
        await self.session.execute(
            update(GiveawayEntry)
            .where(GiveawayEntry.campaign_id == campaign_id)
            .values(status=GiveawayEntryStatus.ARCHIVED)
        )
        model = await self.session.scalar(
            update(GiveawayCampaign)
            .where(GiveawayCampaign.id == campaign_id)
            .values(status=GiveawayCampaignStatus.ARCHIVED, archived_at=now)
            .returning(GiveawayCampaign)
        )
        if model:
            await self.session.refresh(model)
        return self._campaign_dto(model) if model else None

    async def delete_campaign(self, campaign_id: int) -> bool:
        await self.session.execute(
            delete(GiveawayEntry).where(GiveawayEntry.campaign_id == campaign_id)
        )
        result = await self.session.execute(
            delete(GiveawayCampaign).where(GiveawayCampaign.id == campaign_id)
        )
        return bool(result.rowcount)

    async def update_campaign_rules(
        self,
        campaign_id: int,
        rules_text: Optional[str],
    ) -> Optional[GiveawayCampaignDto]:
        model = await self.session.scalar(
            update(GiveawayCampaign)
            .where(GiveawayCampaign.id == campaign_id)
            .values(rules_text=rules_text)
            .returning(GiveawayCampaign)
        )
        if model:
            await self.session.refresh(model)
        return self._campaign_dto(model) if model else None

    async def create_entry(self, entry: GiveawayEntryDto) -> Optional[GiveawayEntryDto]:
        values = {
            "campaign_id": entry.campaign_id,
            "user_telegram_id": entry.user_telegram_id,
            "telegram_username": entry.telegram_username,
            "participant_code": entry.participant_code,
            "transaction_payment_id": entry.transaction_payment_id,
            "plan_id": entry.plan_id,
            "plan_name": entry.plan_name,
            "duration_days": entry.duration_days,
            "purchase_type": entry.purchase_type,
            "entry_source": entry.entry_source,
            "phone": entry.phone,
            "status": entry.status,
        }
        model = await self.session.scalar(
            insert(GiveawayEntry)
            .values(**values)
            .on_conflict_do_nothing()
            .returning(GiveawayEntry)
        )
        if model:
            await self.session.refresh(model)
        return self._entry_dto(model) if model else None

    async def add_manual_entry(
        self,
        entry: GiveawayEntryDto,
    ) -> Optional[GiveawayEntryDto]:
        return await self.create_entry(entry)

    async def get_entry_by_payment(self, payment_id: UUID) -> Optional[GiveawayEntryDto]:
        model = await self.session.scalar(
            select(GiveawayEntry).where(GiveawayEntry.transaction_payment_id == payment_id)
        )
        return self._entry_dto(model) if model else None

    async def get_entry(self, entry_id: int) -> Optional[GiveawayEntryDto]:
        model = await self.session.scalar(
            select(GiveawayEntry).where(GiveawayEntry.id == entry_id)
        )
        return self._entry_dto(model) if model else None

    async def get_entry_for_user(
        self,
        campaign_id: int,
        user_telegram_id: int,
    ) -> Optional[GiveawayEntryDto]:
        model = await self.session.scalar(
            select(GiveawayEntry)
            .where(
                GiveawayEntry.campaign_id == campaign_id,
                GiveawayEntry.user_telegram_id == user_telegram_id,
            )
            .order_by(GiveawayEntry.created_at.desc())
            .limit(1)
        )
        return self._entry_dto(model) if model else None

    async def update_phone(self, entry_id: int, phone: str) -> Optional[GiveawayEntryDto]:
        model = await self.session.scalar(
            update(GiveawayEntry)
            .where(GiveawayEntry.id == entry_id)
            .values(phone=phone)
            .returning(GiveawayEntry)
        )
        if model:
            await self.session.refresh(model)
        return self._entry_dto(model) if model else None

    async def get_entries(self, campaign_id: int) -> list[GiveawayEntryDto]:
        result = await self.session.scalars(
            select(GiveawayEntry)
            .where(
                GiveawayEntry.campaign_id == campaign_id,
                GiveawayEntry.status != GiveawayEntryStatus.ARCHIVED,
            )
            .order_by(GiveawayEntry.created_at.desc())
        )
        return [self._entry_dto(item) for item in cast(list[GiveawayEntry], result.all())]

    async def get_winners(self, campaign_id: int) -> list[GiveawayEntryDto]:
        result = await self.session.scalars(
            select(GiveawayEntry)
            .where(
                GiveawayEntry.campaign_id == campaign_id,
                GiveawayEntry.status == GiveawayEntryStatus.WINNER,
            )
            .order_by(GiveawayEntry.winner_rank)
        )
        return [self._entry_dto(item) for item in cast(list[GiveawayEntry], result.all())]

    async def count_entries(self, campaign_id: int) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(GiveawayEntry)
                .where(
                    GiveawayEntry.campaign_id == campaign_id,
                    GiveawayEntry.status != GiveawayEntryStatus.ARCHIVED,
                )
            )
            or 0
        )

    async def select_winner(
        self,
        campaign_id: int,
        winner_rank: int,
        selected_at: datetime,
    ) -> Optional[GiveawayEntryDto]:
        winning_users = select(GiveawayEntry.user_telegram_id).where(
            GiveawayEntry.campaign_id == campaign_id,
            GiveawayEntry.status == GiveawayEntryStatus.WINNER,
            GiveawayEntry.user_telegram_id.is_not(None),
        )
        candidate = await self.session.scalar(
            select(GiveawayEntry)
            .where(
                GiveawayEntry.campaign_id == campaign_id,
                GiveawayEntry.status == GiveawayEntryStatus.ELIGIBLE,
                or_(
                    GiveawayEntry.user_telegram_id.is_(None),
                    GiveawayEntry.user_telegram_id.not_in(winning_users),
                ),
            )
            .order_by(func.random())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not candidate:
            return None
        candidate.status = GiveawayEntryStatus.WINNER
        candidate.winner_rank = winner_rank
        candidate.selected_at = selected_at
        await self.session.flush()
        await self.session.refresh(candidate)
        return self._entry_dto(candidate)
