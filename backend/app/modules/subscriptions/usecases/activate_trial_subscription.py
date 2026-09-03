from dataclasses import dataclass
from decimal import Decimal

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PurchaseType
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanDto
from app.modules.subscriptions.dto import PlanSnapshot, PurchaseSubscriptionDto, SubscriptionDto
from app.modules.subscriptions.usecases.purchase_subscription import PurchaseSubscriptionUseCase
from app.modules.users import UpdateUserDto, UserDto, UserRepository


@dataclass(frozen=True, kw_only=True)
class ActivateTrialSubscriptionDto:
    plan: PlanDto
    duration_days: int


class ActivateTrialSubscriptionUseCase(UseCase[ActivateTrialSubscriptionDto, SubscriptionDto]):
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
        if not actor.is_trial_available:
            raise ValidationError(f"Trial is not available for user '{actor.id}'")

        plan = data.plan
        subscription = await self._purchase_subscription_use_case(
            actor,
            PurchaseSubscriptionDto(
                user_id=actor.id,
                plan_snapshot=PlanSnapshot(
                    plan_id=plan.id,
                    public_code=plan.public_code,
                    name=plan.name,
                    price_paid=Decimal(0),
                    currency=Currency.USD,
                    duration_days=data.duration_days,
                    traffic_limit=plan.traffic_limit,
                    device_limit=plan.device_limit,
                    traffic_limit_strategy=plan.traffic_limit_strategy,
                    is_trial=True,
                    internal_squads=plan.internal_squads,
                    external_squad=plan.external_squad,
                ),
                duration_days=data.duration_days,
                price_paid=Decimal(0),
                currency=Currency.USD,
                purchase_type=PurchaseType.NEW,
            ),
        )

        # Not atomic with the purchase above (which already committed in its
        # own transaction) -- if this write fails, is_trial_available stays
        # True with a working trial subscription already in place. Trial
        # detection is by subscription state, not this flag, so a retry
        # wouldn't be blocked by the existing trial and would silently
        # refresh it indefinitely, never consuming the flag. Narrow window,
        # accepted rather than restructuring PurchaseSubscriptionUseCase's
        # own transaction boundary for it.
        async with self._uow:
            await self._user_repository.update_fields(
                actor.id, UpdateUserDto(is_trial_available=False)
            )
        return subscription
