from contextlib import suppress
from decimal import Decimal

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PurchaseType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanRepository
from app.modules.pricing import PricingRepository
from app.modules.subscriptions.dto import (
    PlanSnapshot,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)
from app.modules.subscriptions.eligibility import PurchaseEligibility
from app.modules.subscriptions.trials import pick_trial
from app.modules.subscriptions.usecases.purchase_subscription import PurchaseSubscriptionUseCase
from app.modules.users import UpdateUserDto, UserDto, UserRepository


class ActivateTrialSubscriptionUseCase(UseCase[None, SubscriptionDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        user_repository: UserRepository,
        plan_repository: PlanRepository,
        pricing_repository: PricingRepository,
        eligibility: PurchaseEligibility,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._plan_repository = plan_repository
        self._pricing_repository = pricing_repository
        self._eligibility = eligibility
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> SubscriptionDto:
        async with self._uow:
            trial = await pick_trial(
                self._plan_repository, self._pricing_repository, self._eligibility, actor
            )
        # a paid trial is bought through checkout, never activated here
        plan = trial.plan
        duration = plan.free_trial_duration() if plan is not None else None
        if plan is None or duration is None:
            raise ValidationError(
                f"No free trial for user '{actor.id}'", code=ErrorCode.TRIAL_NOT_AVAILABLE
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
                        price_paid=Decimal(0),
                        currency=Currency.USD,
                        duration_days=duration.days,
                        is_trial=True,
                    ),
                    duration_days=duration.days,
                    price_paid=Decimal(0),
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
