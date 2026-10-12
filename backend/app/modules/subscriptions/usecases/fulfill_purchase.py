from dataclasses import replace
from typing import Optional

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PurchaseType
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import OrderFailer
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import PurchaseSubscriptionDto, SubscriptionDto
from app.modules.subscriptions.usecases.purchase_subscription import PurchaseSubscriptionUseCase
from app.modules.users import UserRepository


class FulfillPurchaseUseCase(UseCase[PurchaseSubscriptionDto, Optional[SubscriptionDto]]):
    """Provisions a paid order on behalf of its buyer. None when a free order
    found the buyer at the cap and was failed instead."""

    required_permission = None

    def __init__(
        self,
        user_repository: UserRepository,
        purchase_subscription_use_case: PurchaseSubscriptionUseCase,
        order_failer: OrderFailer,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._purchase_subscription_use_case = purchase_subscription_use_case
        self._order_failer = order_failer
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: PurchaseSubscriptionDto
    ) -> Optional[SubscriptionDto]:
        buyer = await self._user_repository.get_by_id(data.user_id)
        if buyer is None:
            raise NotFoundError(f"User '{data.user_id}' not found", code=ErrorCode.USER_NOT_FOUND)
        # a free order costs nothing to refuse, so it rechecks the cap; a paid one was checked at
        # checkout, and refusing it after the charge would leave the customer paid with nothing
        free_order_key = (
            data.idempotency_key
            if data.purchase_type is PurchaseType.NEW and data.price_paid == 0
            else None
        )
        try:
            subscription = await self._purchase_subscription_use_case(
                buyer,
                replace(
                    data,
                    enforce_subscription_cap=free_order_key is not None,
                    refuse_disabled_target=False,
                ),
            )
        except ValidationError as error:
            if free_order_key is None or error.code is not ErrorCode.SUBSCRIPTION_LIMIT_REACHED:
                raise
        else:
            if data.plan_snapshot.is_trial:
                # spent on delivery, not at checkout: an order that is never
                # paid must not use up the trial (a no-op when already spent)
                async with self._uow:
                    await self._user_repository.spend_trial(buyer.id)
            return subscription
        # failed, not retried: a retry or the reconcile sweep would hit the same cap
        async with self._uow:
            spent = await self._order_failer.fail_unpaid_free_order(free_order_key)
            if spent is not None:
                await self._user_repository.restore_purchase_discount(
                    spent.user_id,
                    spent.percent,
                    spent.promocode_id,
                    from_promocode=spent.from_promocode,
                )
        logger.warning(
            f"{buyer.log} Free order '{free_order_key}' failed: subscription cap reached"
        )
        return None
