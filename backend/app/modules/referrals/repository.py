from decimal import Decimal
from typing import Final, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.referral import Referral
from app.core.db.models.referral_reward import ReferralReward
from app.core.db.models.referral_settings import ReferralSettings
from app.core.enums import ReferralRewardType
from app.core.exceptions import ConflictError
from app.modules.referrals.dto import (
    ReferralDto,
    ReferralRewardDto,
    ReferralSettingsDto,
    UpdateReferralSettingsDto,
)

_SINGLETON_ID: Final[int] = 1


class ReferralRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: Referral) -> ReferralDto:
        return ReferralDto(
            id=row.id,
            referrer_id=row.referrer_id,
            referred_id=row.referred_id,
            level=row.level,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _reward_to_dto(self, row: ReferralReward) -> ReferralRewardDto:
        return ReferralRewardDto(
            id=row.id,
            referral_id=row.referral_id,
            referrer_id=row.referrer_id,
            subscription_id=row.subscription_id,
            type=row.type,
            amount=row.amount,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _settings_to_dto(self, row: Optional[ReferralSettings]) -> ReferralSettingsDto:
        if row is None:
            return ReferralSettingsDto()
        return ReferralSettingsDto(
            id=row.id,
            enabled=row.enabled,
            max_level=row.max_level,
            accrual_strategy=row.accrual_strategy,
            reward_type=row.reward_type,
            reward_amounts={int(k): Decimal(str(v)) for k, v in row.reward_amounts.items()},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_by_referred_id(self, referred_id: int) -> Optional[ReferralDto]:
        stmt = select(Referral).where(Referral.referred_id == referred_id)
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row is not None else None

    async def has_referrer(self, user_id: int) -> bool:
        return await self.get_by_referred_id(user_id) is not None

    async def create_referral(
        self, *, referrer_id: int, referred_id: int, level: int
    ) -> ReferralDto:
        row = Referral(referrer_id=referrer_id, referred_id=referred_id, level=level)
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError as error:
            raise ConflictError(f"User '{referred_id}' already has a referrer") from error
        return self._to_dto(row)

    async def count_by_level(self, referrer_id: int) -> dict[int, int]:
        stmt = (
            select(Referral.level, func.count())
            .where(Referral.referrer_id == referrer_id)
            .group_by(Referral.level)
        )
        rows = await self.session.execute(stmt)
        return {int(level): int(count) for level, count in rows.all()}

    async def create_reward(
        self,
        *,
        referral_id: int,
        referrer_id: int,
        subscription_id: int,
        type: ReferralRewardType,
        amount: Decimal,
    ) -> ReferralRewardDto:
        row = ReferralReward(
            referral_id=referral_id,
            referrer_id=referrer_id,
            subscription_id=subscription_id,
            type=type,
            amount=amount,
        )
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError as error:
            raise ConflictError(
                f"Reward already granted for subscription '{subscription_id}' "
                f"and referral '{referral_id}'"
            ) from error
        return self._reward_to_dto(row)

    async def list_rewards_by_referrer(self, referrer_id: int) -> list[ReferralRewardDto]:
        stmt = (
            select(ReferralReward)
            .where(ReferralReward.referrer_id == referrer_id)
            .order_by(ReferralReward.created_at.desc())
        )
        rows = await self.session.scalars(stmt)
        return [self._reward_to_dto(row) for row in rows]

    async def _get_or_create_settings(self) -> ReferralSettings:
        row = await self.session.get(ReferralSettings, _SINGLETON_ID)
        if row is None:
            row = ReferralSettings(id=_SINGLETON_ID)
            self.session.add(row)
        return row

    async def get_settings(self) -> ReferralSettingsDto:
        row = await self.session.get(ReferralSettings, _SINGLETON_ID)
        return self._settings_to_dto(row)

    async def update_settings(self, data: UpdateReferralSettingsDto) -> ReferralSettingsDto:
        row = await self._get_or_create_settings()

        if data.enabled is not None:
            row.enabled = data.enabled
        if data.max_level is not None:
            row.max_level = data.max_level
        if data.accrual_strategy is not None:
            row.accrual_strategy = data.accrual_strategy
        if data.reward_type is not None:
            row.reward_type = data.reward_type
        if data.reward_amounts is not None:
            row.reward_amounts = {str(k): str(v) for k, v in data.reward_amounts.items()}

        await self.session.flush()
        await self.session.refresh(row)
        return self._settings_to_dto(row)
