from decimal import Decimal
from typing import Final

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import ReferralRewardStrategy
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.pricing import PricingRepository
from app.modules.referrals.dto import ReferralSettingsDto, UpdateReferralSettingsDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserDto

_MAX_PERCENT: Final[Decimal] = Decimal(100)
_MIN_REWARD: Final[Decimal] = Decimal(1)


def _check_amounts(
    amounts: dict[int, Decimal],
    *,
    strategy: ReferralRewardStrategy,
    enabled: bool,
    max_level: int,
) -> None:
    if any(amount < 0 for amount in amounts.values()):
        raise ValidationError("A reward can't be negative")
    if strategy is ReferralRewardStrategy.PERCENT and any(
        amount > _MAX_PERCENT for amount in amounts.values()
    ):
        raise ValidationError("A percent reward can't exceed 100")
    # a level that shouldn't earn is switched off via max_level, not a zero;
    # a disabled program may keep blanks, e.g. right after a reset
    if not enabled:
        return
    for level in range(1, max_level + 1):
        if amounts.get(level, Decimal(0)) < _MIN_REWARD:
            raise ValidationError(f"Level {level} reward must be at least 1")


class UpdateReferralSettingsUseCase(UseCase[UpdateReferralSettingsDto, ReferralSettingsDto]):
    required_permission = Permission.REFERRALS_SETTINGS_MANAGE

    def __init__(
        self,
        referral_repository: ReferralRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
    ) -> None:
        self._referral_repository = referral_repository
        self._pricing_repository = pricing_repository
        self._uow = uow

    async def _execute(
        self, actor: UserDto, data: UpdateReferralSettingsDto
    ) -> ReferralSettingsDto:
        async with self._uow:
            current = await self._referral_repository.get_settings()
            strategy = data.reward_strategy or current.reward_strategy
            amounts = (
                data.reward_amounts if data.reward_amounts is not None else current.reward_amounts
            )
            enabled = data.enabled if data.enabled is not None else current.enabled
            max_level = data.max_level or current.max_level
            _check_amounts(amounts, strategy=strategy, enabled=enabled, max_level=max_level)
            updated = await self._referral_repository.update_settings(data)
            pricing = await self._pricing_repository.get_settings()
        logger.info(f"{actor.log} Updated referral settings")
        return updated.model_copy(update={"anchor_currency": pricing.anchor_currency})
