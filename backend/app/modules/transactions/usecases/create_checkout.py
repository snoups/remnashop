import hmac
from datetime import timedelta
from typing import Final, Optional
from uuid import uuid4

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    DiscountSource,
    PaymentGatewayType,
    PlanAvailability,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.gateways import GatewaysRepository
from app.modules.plans import PlanDto, PlanRepository, is_plan_purchasable_by
from app.modules.pricing import PricingRepository
from app.modules.referrals import ReferralRepository
from app.modules.settings import SettingsRepository
from app.modules.subscriptions import (
    PlanSnapshot,
    SubscriptionRepository,
    purchase_subscription_task,
)
from app.modules.transactions.dto import (
    CheckoutResultDto,
    CreateCheckoutDto,
    CreateTransactionDto,
    PriceQuote,
)
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.gateways.registry import GATEWAY_REGISTRY, gateway_currency
from app.modules.transactions.pricing import quote_price
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserDto, UserRepository

_ORDER_TTL: Final[timedelta] = timedelta(minutes=30)


def _link_code_matches(plan: PlanDto, plan_code: Optional[str]) -> bool:
    if plan.availability is not PlanAvailability.LINK:
        return True
    return plan_code is not None and hmac.compare_digest(plan_code, plan.public_code)


class CreateCheckoutUseCase(UseCase[CreateCheckoutDto, CheckoutResultDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        plan_repository: PlanRepository,
        user_repository: UserRepository,
        gateways_repository: GatewaysRepository,
        transaction_repository: TransactionRepository,
        subscription_repository: SubscriptionRepository,
        settings_repository: SettingsRepository,
        referral_repository: ReferralRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        gateway_factory: PaymentGatewayFactory,
    ) -> None:
        self._plan_repository = plan_repository
        self._user_repository = user_repository
        self._gateways_repository = gateways_repository
        self._transaction_repository = transaction_repository
        self._subscription_repository = subscription_repository
        self._settings_repository = settings_repository
        self._referral_repository = referral_repository
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._gateway_factory = gateway_factory

    @staticmethod
    def _resolve_customer_email(
        data: CreateCheckoutDto, user: UserDto, gateway_settings: dict[str, str]
    ) -> Optional[str]:
        customer_email = data.customer_email or user.email
        gateway_class = GATEWAY_REGISTRY[data.gateway_type]
        if customer_email is None and gateway_class.requires_customer_email(gateway_settings):
            raise ValidationError(
                f"Gateway '{data.gateway_type.value}' requires a customer email",
                code=ErrorCode.GATEWAY_EMAIL_REQUIRED,
            )
        return customer_email

    async def _execute(self, actor: UserDto, data: CreateCheckoutDto) -> CheckoutResultDto:
        async with self._uow:
            if data.user_id != actor.id and not actor.is_privileged:
                raise PermissionDeniedError

            if data.gateway_type is PaymentGatewayType.TELEGRAM_STARS:
                raise ValidationError(
                    "Telegram Stars checkout runs in the bot, not the web API",
                    code=ErrorCode.TELEGRAM_STARS_BOT_ONLY,
                )
            if data.gateway_type not in GATEWAY_REGISTRY:
                raise ValidationError(
                    f"Gateway '{data.gateway_type.value}' is not yet supported",
                    code=ErrorCode.GATEWAY_NOT_SUPPORTED,
                )
            gateway_settings = await self._gateways_repository.get_raw_settings(data.gateway_type)
            if data.currency is not gateway_currency(data.gateway_type, gateway_settings):
                raise ValidationError(
                    f"Gateway '{data.gateway_type.value}' does not settle '{data.currency.value}'",
                    code=ErrorCode.GATEWAY_CURRENCY_UNSUPPORTED,
                )

            plan = await self._plan_repository.get_by_id(data.plan_id)
            user = await self._user_repository.get_by_id(data.user_id)
            if user is None:
                raise NotFoundError(
                    f"User '{data.user_id}' not found", code=ErrorCode.USER_NOT_FOUND
                )

            customer_email = self._resolve_customer_email(data, user, gateway_settings)

            has_purchase_history = await self._subscription_repository.has_any_subscription(
                user.id, include_trial=False
            )
            has_referrer = await self._referral_repository.has_referrer(user.id)
            if not is_plan_purchasable_by(
                plan, user, has_purchase_history=has_purchase_history, has_referrer=has_referrer
            ) or not _link_code_matches(plan, data.plan_code):
                # Same answer as a missing plan: a distinct one would let anyone
                # walk plan ids and learn which hidden plans exist.
                raise NotFoundError(
                    f"Plan '{data.plan_id}' not found", code=ErrorCode.PLAN_NOT_FOUND
                )

        await self._validate_provisioning_preconditions(data)

        async with self._uow:
            rates = await self._pricing_repository.get_rate_table()
            quote = quote_price(plan, data.duration_days, data.currency, user, rates)
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

            is_free = quote.final_price == 0
        if not is_free:
            await self._validate_gateway_availability(data.gateway_type)

        async with self._uow:
            # The one-shot discount is spent with the order that quoted it, in
            # the same transaction -- a second checkout racing this one finds
            # it gone and has to re-quote.
            await self._spend_purchase_discount(quote, user)
            order = await self._transaction_repository.create(
                CreateTransactionDto(
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
                    discount_promocode_id=quote.discount_promocode_id,
                    customer_email=customer_email,
                    idempotency_key=uuid4().hex,
                    expires_at=datetime_now() + _ORDER_TTL,
                )
            )

            if is_free:
                order = await self._transaction_repository.mark_status(
                    order.id, TransactionStatus.PAID
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

        gateway = self._gateway_factory.build(data.gateway_type, gateway_settings)
        intent = await gateway.create_payment(order)

        async with self._uow:
            await self._transaction_repository.mark_status(
                order.id,
                TransactionStatus.PENDING,
                external_payment_id=intent.provider_payment_id,
            )

        return CheckoutResultDto(order_id=order.id, confirmation_url=intent.confirmation_url)

    async def _spend_purchase_discount(self, quote: PriceQuote, user: UserDto) -> None:
        if quote.discount_source is not DiscountSource.PURCHASE:
            return
        if not await self._user_repository.spend_purchase_discount(user.id, user.purchase_discount):
            raise ValidationError(
                "The purchase discount was already used, please retry",
                code=ErrorCode.PURCHASE_DISCOUNT_USED,
            )

    async def _validate_gateway_availability(self, gateway_type: PaymentGatewayType) -> None:
        async with self._uow:
            gateway_config = await self._gateways_repository.get_by_type(gateway_type)
            if not gateway_config.is_active or not gateway_config.is_configured:
                raise ValidationError(
                    f"Gateway '{gateway_type.value}' is not available",
                    code=ErrorCode.GATEWAY_NOT_AVAILABLE,
                )

    async def _validate_provisioning_preconditions(self, data: CreateCheckoutDto) -> None:
        # Belt-and-braces: PurchaseSubscriptionUseCase re-checks the target
        # subscription under its own lock. The concurrent-subscription cap is
        # enforced only here -- a paid order is provisioned even if the cap
        # filled up before the worker ran (enforce_subscription_cap=False).
        async with self._uow:
            if data.purchase_type is PurchaseType.NEW:
                if data.target_subscription_id is not None:
                    raise ValidationError(
                        "target_subscription_id is forbidden for a NEW purchase",
                        code=ErrorCode.TARGET_SUBSCRIPTION_FORBIDDEN,
                    )
                shop_settings = await self._settings_repository.get_shop_settings()
                max_active = shop_settings.max_active_subscriptions
                if max_active is not None:
                    active = await self._subscription_repository.get_active_by_user(data.user_id)
                    if len(active) >= max_active:
                        raise ValidationError(
                            f"User '{data.user_id}' is already at the concurrent-subscription cap",
                            code=ErrorCode.SUBSCRIPTION_LIMIT_REACHED,
                        )
                return

        await self._validate_target_subscription(data)

    async def _validate_target_subscription(self, data: CreateCheckoutDto) -> None:
        async with self._uow:
            if data.target_subscription_id is None:
                raise ValidationError(
                    f"target_subscription_id is required for a {data.purchase_type.value}",
                    code=ErrorCode.TARGET_SUBSCRIPTION_REQUIRED,
                )

            try:
                target = await self._subscription_repository.get_by_id(data.target_subscription_id)
            except NotFoundError as error:
                raise ValidationError(
                    "target_subscription_id does not belong to this user",
                    code=ErrorCode.TARGET_SUBSCRIPTION_NOT_OWNED,
                ) from error
            if target.user_id != data.user_id:
                raise ValidationError(
                    "target_subscription_id does not belong to this user",
                    code=ErrorCode.TARGET_SUBSCRIPTION_NOT_OWNED,
                )
            if target.status is SubscriptionStatus.DELETED:
                raise ValidationError(
                    f"Cannot {data.purchase_type.value.lower()} a deleted subscription",
                    code=ErrorCode.SUBSCRIPTION_DELETED,
                )

            if data.purchase_type is PurchaseType.RENEW:
                if target.plan_snapshot.plan_id != data.plan_id:
                    raise ValidationError(
                        "Renewing a different plan is a CHANGE, not a RENEW",
                        code=ErrorCode.RENEW_PLAN_MISMATCH,
                    )
            elif data.duration_days <= 0:
                raise ValidationError(
                    "duration_days must be positive", code=ErrorCode.DURATION_NOT_POSITIVE
                )
