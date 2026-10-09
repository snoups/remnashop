from decimal import Decimal
from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.constants import MAX_POINTS_BALANCE
from app.core.db.uow import UnitOfWork
from app.core.enums import ReferralRewardStrategy, ReferralRewardType
from app.core.error_codes import ErrorCode
from app.core.events import set_fields
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.pricing import PricingRepository
from app.modules.referrals.dto import (
    MAX_BONUS_DAYS,
    ReferralSettingsDto,
    UpdateReferralSettingsDto,
)
from app.modules.referrals.events import ReferralSettingsChangedEvent
from app.modules.referrals.repository import ReferralRepository

_MAX_PERCENT: Final[Decimal] = Decimal(100)
_MIN_REWARD: Final[Decimal] = Decimal(1)
# an amount reward's ceiling: MAX_BONUS_DAYS for days, Numeric(12, 0) for points
_MAX_AMOUNT_REWARD: Final[dict[ReferralRewardType, Decimal]] = {
    ReferralRewardType.EXTRA_DAYS: Decimal(MAX_BONUS_DAYS),
    ReferralRewardType.POINTS: MAX_POINTS_BALANCE,
}


def _check_amounts(
    amounts: dict[int, Decimal],
    *,
    strategy: ReferralRewardStrategy,
    reward_type: ReferralRewardType,
    enabled: bool,
    max_level: int,
) -> None:
    if any(amount < 0 for amount in amounts.values()):
        raise ValidationError("A reward can't be negative", code=ErrorCode.REFERRAL_REWARD_NEGATIVE)
    if strategy is ReferralRewardStrategy.PERCENT and any(
        amount > _MAX_PERCENT for amount in amounts.values()
    ):
        raise ValidationError(
            "A percent reward can't exceed 100", code=ErrorCode.REFERRAL_REWARD_PERCENT_TOO_HIGH
        )
    if strategy is ReferralRewardStrategy.AMOUNT and any(
        amount > _MAX_AMOUNT_REWARD[reward_type] for amount in amounts.values()
    ):
        raise ValidationError(
            f"An amount reward can't exceed {_MAX_AMOUNT_REWARD[reward_type]}",
            code=ErrorCode.REFERRAL_REWARD_TOO_HIGH,
        )
    # a level that shouldn't earn is switched off via max_level, not a zero;
    # a disabled program may keep blanks, e.g. right after a reset
    if not enabled:
        return
    for level in range(1, max_level + 1):
        if amounts.get(level, Decimal(0)) < _MIN_REWARD:
            raise ValidationError(
                f"Level {level} reward must be at least 1", code=ErrorCode.REFERRAL_REWARD_TOO_LOW
            )


class UpdateReferralSettingsUseCase(UseCase[UpdateReferralSettingsDto, ReferralSettingsDto]):
    required_permission = Permission.REFERRALS_SETTINGS_MANAGE

    def __init__(
        self,
        referral_repository: ReferralRepository,
        pricing_repository: PricingRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._referral_repository = referral_repository
        self._pricing_repository = pricing_repository
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: UpdateReferralSettingsDto) -> ReferralSettingsDto:
        async with self._uow:
            current = await self._referral_repository.get_settings()
            strategy = data.reward_strategy or current.reward_strategy
            amounts = (
                data.reward_amounts if data.reward_amounts is not None else current.reward_amounts
            )
            enabled = data.enabled if data.enabled is not None else current.enabled
            max_level = data.max_level or current.max_level
            _check_amounts(
                amounts,
                strategy=strategy,
                reward_type=data.reward_type or current.reward_type,
                enabled=enabled,
                max_level=max_level,
            )
            updated = await self._referral_repository.update_settings(data)
            await self._event_publisher.publish(
                ReferralSettingsChangedEvent(
                    user=actor, action="update", changed_fields=set_fields(data)
                )
            )
            pricing = await self._pricing_repository.get_settings()
        logger.info(f"{actor.log} Updated referral settings")
        return updated.model_copy(update={"anchor_currency": pricing.anchor_currency})
