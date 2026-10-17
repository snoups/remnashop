import math
from decimal import Decimal

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PurchaseType
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.plans import PlanRepository
from app.modules.subscriptions.dto import (
    ChangeSubscriptionPlanDto,
    PlanSnapshot,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)
from app.modules.subscriptions.eligibility import get_manageable_subscription
from app.modules.subscriptions.events import SubscriptionPlanChangedByAdminEvent
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases.purchase_subscription import PurchaseSubscriptionUseCase
from app.modules.users import UserRepository


class ChangeSubscriptionPlanUseCase(UseCase[ChangeSubscriptionPlanDto, SubscriptionDto]):
    required_permission = Permission.SUBSCRIPTIONS_PLAN_CHANGE

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        plan_repository: PlanRepository,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._plan_repository = plan_repository
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: ChangeSubscriptionPlanDto) -> SubscriptionDto:
        async with self._uow:
            old = await get_manageable_subscription(
                self._subscription_repository, self._user_repository, actor, data.subscription_id
            )
            owner = await self._user_repository.find_by_id(old.user_id)
            if owner is None:
                raise NotFoundError(
                    f"User '{old.user_id}' not found", code=ErrorCode.USER_NOT_FOUND
                )
            plan = await self._plan_repository.get_by_id(data.plan_id)

        if data.duration_days is None:
            remaining_days = (old.expire_at - datetime_now()).total_seconds() / 86400
            duration_days = max(1, math.ceil(remaining_days))
        else:
            duration_days = data.duration_days

        changed = await self._purchase_subscription_use_case(
            actor,
            PurchaseSubscriptionDto(
                user_id=old.user_id,
                plan_snapshot=PlanSnapshot.from_plan(
                    plan,
                    price_paid=Decimal(0),
                    currency=Currency.USD,
                    duration_days=duration_days,
                ),
                duration_days=duration_days,
                price_paid=Decimal(0),
                currency=Currency.USD,
                purchase_type=PurchaseType.CHANGE,
                target_subscription_id=old.id,
                keep_expire_at=data.duration_days is None,
                publish_event=False,
            ),
        )

        async with self._uow:
            await self._event_publisher.publish(
                SubscriptionPlanChangedByAdminEvent(
                    actor=actor,
                    target=owner,
                    subscription_id=changed.id,
                    previous_subscription_id=old.id,
                    previous_plan_snapshot=old.plan_snapshot.to_json(),
                    plan_id=plan.id,
                    duration_days=data.duration_days,
                )
            )

        logger.info(
            f"{actor.log} Changed subscription '{old.id}' to plan '{plan.id}' as '{changed.id}'"
        )
        return changed
