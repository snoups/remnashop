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
from app.modules.plans import PlanRepository
from app.modules.subscriptions.dto import (
    GrantSubscriptionDto,
    PlanSnapshot,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)
from app.modules.subscriptions.events import SubscriptionGrantedEvent
from app.modules.subscriptions.usecases.purchase_subscription import PurchaseSubscriptionUseCase
from app.modules.users import UserRepository


class GrantSubscriptionUseCase(UseCase[GrantSubscriptionDto, SubscriptionDto]):
    required_permission = Permission.SUBSCRIPTIONS_GRANT

    def __init__(
        self,
        user_repository: UserRepository,
        plan_repository: PlanRepository,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._plan_repository = plan_repository
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: GrantSubscriptionDto) -> SubscriptionDto:
        async with self._uow:
            recipient = await self._user_repository.find_by_id(data.user_id)
            if recipient is None:
                raise NotFoundError(
                    f"User '{data.user_id}' not found", code=ErrorCode.USER_NOT_FOUND
                )
            plan = await self._plan_repository.get_by_id(data.plan_id)

        subscription = await self._purchase_subscription_use_case(
            actor,
            PurchaseSubscriptionDto(
                user_id=recipient.id,
                plan_snapshot=PlanSnapshot.from_plan(
                    plan,
                    price_paid=Decimal(0),
                    currency=Currency.USD,
                    duration_days=data.duration_days,
                ),
                duration_days=data.duration_days,
                price_paid=Decimal(0),
                currency=Currency.USD,
                purchase_type=PurchaseType.NEW,
                enforce_subscription_cap=False,
                publish_event=False,
            ),
        )

        async with self._uow:
            await self._event_publisher.publish(
                SubscriptionGrantedEvent(
                    actor=actor,
                    target=recipient,
                    subscription_id=subscription.id,
                    plan_id=plan.id,
                    duration_days=data.duration_days,
                )
            )

        logger.info(
            f"{actor.log} Granted subscription '{subscription.id}' "
            f"(plan '{plan.id}', {data.duration_days}d) to user '{recipient.id}'"
        )
        return subscription
