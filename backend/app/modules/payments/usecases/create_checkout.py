from datetime import timedelta
from typing import Final
from uuid import uuid4

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    PaymentGatewayType,
    PaymentOrderStatus,
    PurchaseType,
    SubscriptionStatus,
)
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.gateways import GatewaysRepository
from app.modules.payments.dto import CheckoutResultDto, CreateCheckoutDto, CreatePaymentOrderDto
from app.modules.payments.gateways.base import PaymentGateway
from app.modules.payments.gateways.yookassa import YooKassaGateway
from app.modules.payments.pricing import quote_price
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.plans import PlanRepository, is_plan_purchasable_by
from app.modules.settings import SettingsRepository
from app.modules.subscriptions import (
    PlanSnapshot,
    SubscriptionRepository,
    purchase_subscription_task,
)
from app.modules.users import UserDto, UserRepository

_ORDER_TTL: Final[timedelta] = timedelta(minutes=30)

# Which currencies each gateway actually settles -- YooKassa is a Russian
# processor, RUB only. Extend this map (not a DB CheckConstraint -- see the
# spec's §9) the day a second gateway/currency pairing ships.
_GATEWAY_CURRENCIES: Final[dict[PaymentGatewayType, frozenset[Currency]]] = {
    PaymentGatewayType.YOOKASSA: frozenset({Currency.RUB}),
}


class CreateCheckoutUseCase(UseCase[CreateCheckoutDto, CheckoutResultDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        plan_repository: PlanRepository,
        user_repository: UserRepository,
        gateways_repository: GatewaysRepository,
        payment_order_repository: PaymentOrderRepository,
        subscription_repository: SubscriptionRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
    ) -> None:
        self._plan_repository = plan_repository
        self._user_repository = user_repository
        self._gateways_repository = gateways_repository
        self._payment_order_repository = payment_order_repository
        self._subscription_repository = subscription_repository
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: CreateCheckoutDto) -> CheckoutResultDto:
        if data.user_id != actor.id and not actor.is_privileged:
            raise PermissionDeniedError

        if data.gateway_type is not PaymentGatewayType.YOOKASSA:
            raise ValidationError(f"Gateway '{data.gateway_type.value}' is not yet supported")

        if data.currency not in _GATEWAY_CURRENCIES[data.gateway_type]:
            raise ValidationError(
                f"Gateway '{data.gateway_type.value}' does not settle '{data.currency.value}'"
            )

        plan = await self._plan_repository.get_by_id(data.plan_id)
        user = await self._user_repository.get_by_id(data.user_id)
        if user is None:
            raise NotFoundError(f"User '{data.user_id}' not found")

        customer_email = data.customer_email or user.email

        has_purchase_history = await self._subscription_repository.has_any_subscription(
            user.id, include_trial=False
        )
        if not is_plan_purchasable_by(plan, user, has_purchase_history=has_purchase_history):
            raise ValidationError("Plan is not available for purchase")

        await self._validate_provisioning_preconditions(data)

        quote = quote_price(plan, data.duration_days, data.currency, user)
        plan_snapshot = PlanSnapshot(
            plan_id=plan.id,
            public_code=plan.public_code,
            name=plan.name,
            price_paid=quote.final_price,
            currency=data.currency,
            duration_days=data.duration_days,
            traffic_limit=plan.traffic_limit,
            device_limit=plan.device_limit,
            traffic_limit_strategy=plan.traffic_limit_strategy,
            is_trial=plan.is_trial,
            internal_squads=plan.internal_squads,
            external_squad=plan.external_squad,
        )

        async with self._uow:
            order = await self._payment_order_repository.create(
                CreatePaymentOrderDto(
                    user_id=data.user_id,
                    plan_id=data.plan_id,
                    plan_snapshot=plan_snapshot,
                    duration_days=data.duration_days,
                    currency=data.currency,
                    purchase_type=data.purchase_type,
                    target_subscription_id=data.target_subscription_id,
                    gateway_type=data.gateway_type,
                    base_price=quote.base_price,
                    discount_percent=quote.discount_percent,
                    discount_source=quote.discount_source,
                    final_price=quote.final_price,
                    customer_email=customer_email,
                    idempotency_key=uuid4().hex,
                    expires_at=datetime_now() + _ORDER_TTL,
                )
            )

            is_free = quote.final_price == 0
            if is_free:
                order = await self._payment_order_repository.mark_status(
                    order.id, PaymentOrderStatus.PAID
                )

        if is_free:
            # Dispatched after the `async with` block above has exited (commit
            # already durable) -- `.kiq()` is a real external side effect
            # (a message sent to Redis), not a same-transaction outbox write
            # like EventPublisher.publish(). Firing it before the commit is
            # guaranteed durable risks dispatching a task for an order that
            # then fails to persist.
            await purchase_subscription_task.kiq(  # type: ignore[call-overload]
                user_id=order.user_id,
                plan_snapshot=order.plan_snapshot.to_json(),
                duration_days=order.duration_days,
                price_paid=str(order.final_price),
                base_price=str(order.base_price),
                currency=order.currency.value,
                purchase_type=order.purchase_type.value,
                target_subscription_id=order.target_subscription_id,
                idempotency_key=order.idempotency_key,
            )
            return CheckoutResultDto(order_id=order.id, confirmation_url=None)

        settings = await self._gateways_repository.get_raw_settings(data.gateway_type)
        gateway: PaymentGateway = YooKassaGateway()
        external_payment_id, confirmation_url = await gateway.create_payment(order, settings)

        async with self._uow:
            await self._payment_order_repository.mark_status(
                order.id, PaymentOrderStatus.PENDING, external_payment_id=external_payment_id
            )

        return CheckoutResultDto(order_id=order.id, confirmation_url=confirmation_url)

    async def _validate_provisioning_preconditions(self, data: CreateCheckoutDto) -> None:
        # Belt-and-braces: PurchaseSubscriptionUseCase re-checks all of this
        # under its own lock. Checking here too means an order that would
        # deterministically fail provisioning never gets the customer charged;
        # the TOCTOU window until the worker runs is the usecase's problem.
        if data.purchase_type is PurchaseType.NEW:
            if data.target_subscription_id is not None:
                raise ValidationError("target_subscription_id is forbidden for a NEW purchase")
            shop_settings = await self._settings_repository.get_shop_settings()
            max_active = shop_settings.max_active_subscriptions
            if max_active is not None:
                active = await self._subscription_repository.get_active_by_user(data.user_id)
                if len(active) >= max_active:
                    raise ValidationError(
                        f"User '{data.user_id}' is already at the concurrent-subscription cap"
                    )
            return

        await self._validate_target_subscription(data)

    async def _validate_target_subscription(self, data: CreateCheckoutDto) -> None:
        if data.target_subscription_id is None:
            raise ValidationError(
                f"target_subscription_id is required for a {data.purchase_type.value}"
            )

        try:
            target = await self._subscription_repository.get_by_id(data.target_subscription_id)
        except NotFoundError as error:
            raise ValidationError("target_subscription_id does not belong to this user") from error
        if target.user_id != data.user_id:
            raise ValidationError("target_subscription_id does not belong to this user")
        if target.status is SubscriptionStatus.DELETED:
            raise ValidationError(
                f"Cannot {data.purchase_type.value.lower()} a deleted subscription"
            )

        if data.purchase_type is PurchaseType.RENEW:
            if target.plan_snapshot.plan_id != data.plan_id:
                raise ValidationError("Renewing a different plan is a CHANGE, not a RENEW")
        elif data.duration_days <= 0:
            raise ValidationError("duration_days must be positive")
