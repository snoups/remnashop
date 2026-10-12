from contextlib import suppress
from decimal import Decimal

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PurchaseType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import (
    ActivateTrialSubscriptionDto,
    PlanSnapshot,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)
from app.modules.subscriptions.usecases.purchase_subscription import PurchaseSubscriptionUseCase
from app.modules.users import UpdateUserDto, UserDto, UserRepository


class ActivateTrialSubscriptionUseCase(
    UseCase[ActivateTrialSubscriptionDto, SubscriptionDto, UserDto]
):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        user_repository: UserRepository,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._uow = uow

    async def _execute(self, actor: UserDto, data: ActivateTrialSubscriptionDto) -> SubscriptionDto:
        duration = data.plan.free_trial_duration()
        if duration is None:
            raise ValidationError(
                f"Plan '{data.plan.id}' has no free trial", code=ErrorCode.TRIAL_NOT_AVAILABLE
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
                        data.plan,
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
