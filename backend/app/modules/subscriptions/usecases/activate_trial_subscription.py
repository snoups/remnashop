from contextlib import suppress

from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PurchaseType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanRepository
from app.modules.pricing import PricingRepository
from app.modules.settings import SettingsRepository, is_channel_member
from app.modules.subscriptions.dto import (
    ActivateTrialDto,
    PlanSnapshot,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)
from app.modules.subscriptions.eligibility import PurchaseEligibility
from app.modules.subscriptions.trials import pick_trial
from app.modules.subscriptions.usecases.purchase_subscription import PurchaseSubscriptionUseCase
from app.modules.users import UpdateUserDto, UserDto, UserRepository


class ActivateTrialSubscriptionUseCase(UseCase[ActivateTrialDto, SubscriptionDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        user_repository: UserRepository,
        plan_repository: PlanRepository,
        pricing_repository: PricingRepository,
        settings_repository: SettingsRepository,
        eligibility: PurchaseEligibility,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._plan_repository = plan_repository
        self._pricing_repository = pricing_repository
        self._settings_repository = settings_repository
        self._eligibility = eligibility
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._uow = uow

    async def _execute(self, actor: UserDto, data: ActivateTrialDto) -> SubscriptionDto:
        async with self._uow:
            trial = await pick_trial(
                self._plan_repository, self._pricing_repository, self._eligibility, actor
            )
            requirements = await self._settings_repository.get_bot_requirements()
            bot = await self._settings_repository.get_bot_settings()
        # a paid trial is bought through checkout, never activated here
        plan = trial.plan
        duration = plan.free_trial_duration() if plan is not None else None
        if plan is None or duration is None:
            raise ValidationError(
                f"No free trial for user '{actor.id}'", code=ErrorCode.TRIAL_NOT_AVAILABLE
            )

        channel_id = requirements.channel_id
        if (
            data.mini_app
            and actor.telegram_id is not None
            and requirements.channel_required
            and requirements.trial_channel_guard
            and channel_id is not None
            and bot.token is not None
            and not await is_channel_member(
                bot.token.get_secret_value(), bot.proxy, channel_id, actor.telegram_id
            )
        ):
            raise ValidationError(
                f"User '{actor.id}' is not in the required channel",
                code=ErrorCode.TRIAL_CHANNEL_REQUIRED,
            )

        # Spend the flag before provisioning, not after: actor is loaded per
        # request, so two concurrent taps both read is_trial_available=True.
        async with self._uow:
            claimed = await self._user_repository.spend_trial(actor.id)
        if not claimed:
            raise ValidationError(
                f"Trial is not available for user '{actor.id}'", code=ErrorCode.TRIAL_NOT_AVAILABLE
            )

        try:
            return await self._purchase_subscription_use_case(
                actor,
                PurchaseSubscriptionDto(
                    user_id=actor.id,
                    plan_snapshot=PlanSnapshot.from_plan(
                        plan,
                        price_paid=ZERO_AMOUNT,
                        currency=Currency.USD,
                        duration_days=duration.days,
                        is_trial=True,
                    ),
                    duration_days=duration.days,
                    price_paid=ZERO_AMOUNT,
                    currency=Currency.USD,
                    purchase_type=PurchaseType.NEW,
                ),
            )
        except Exception:
            # NewPurchase disables the panel user it minted on failure, so
            # nothing was granted; the trial goes back for a retry
            with suppress(Exception):
                async with self._uow:
                    await self._user_repository.update_fields(
                        actor.id, UpdateUserDto(is_trial_available=True)
                    )
            raise
