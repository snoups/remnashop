import hmac
from datetime import timedelta
from functools import partial
from typing import Final, Optional
from uuid import uuid4

from loguru import logger

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
from app.core.exceptions import (
    NotFoundError,
    PaymentGatewayError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.ports import PromocodeLiveness
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.gateways import GatewayRepository
from app.modules.plans import PlanDto, PlanRepository
from app.modules.pricing import PricingRepository
from app.modules.settings import GetAccessSettingsUseCase
from app.modules.subscriptions import (
    PlanSnapshot,
    PurchaseEligibility,
    PurchaseSubscriptionDispatch,
    SubscriptionRepository,
    get_owned_target,
)
from app.modules.transactions.dto import (
    CheckoutResultDto,
    CreateCheckoutDto,
    CreateTransactionDto,
    PriceQuote,
    TransactionDto,
)
from app.modules.transactions.fulfillment import dispatch_fulfillment
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.gateways.registry import GATEWAY_REGISTRY, gateway_currency
from app.modules.transactions.pricing import quote_price
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.waitlist_repository import WaitlistRepository
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
        gateway_repository: GatewayRepository,
        transaction_repository: TransactionRepository,
        subscription_repository: SubscriptionRepository,
        eligibility: PurchaseEligibility,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        gateway_factory: PaymentGatewayFactory,
        purchase_dispatch: PurchaseSubscriptionDispatch,
        promocode_liveness: PromocodeLiveness,
        get_access_settings: GetAccessSettingsUseCase,
        waitlist_repository: WaitlistRepository,
    ) -> None:
        self._plan_repository = plan_repository
        self._user_repository = user_repository
        self._gateway_repository = gateway_repository
        self._transaction_repository = transaction_repository
        self._subscription_repository = subscription_repository
        self._eligibility = eligibility
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._gateway_factory = gateway_factory
        self._purchase_dispatch = purchase_dispatch
        self._promocode_liveness = promocode_liveness
        self._get_access_settings = get_access_settings
        self._waitlist_repository = waitlist_repository

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
        if not (await self._get_access_settings.system()).payments_enabled:
            # own transaction, so the refusal below doesn't roll it back
            async with self._uow:
                await self._waitlist_repository.add(actor.id)
            raise PermissionDeniedError("Payments are disabled", code=ErrorCode.PAYMENTS_DISABLED)

        async with self._uow:
            gateway_settings = await self._load_gateway_settings(data)
            plan, user = await self._load_purchasable_plan(actor.id, data)
            customer_email = self._resolve_customer_email(data, user, gateway_settings)

        await self._validate_provisioning_preconditions(actor.id, data)
        user = await self._drop_dead_promocode_discounts(user)

        async with self._uow:
            rates = await self._pricing_repository.get_rate_table()
            quote = quote_price(plan, data.duration_days, data.currency, user, rates)

        is_free = quote.final_price == 0
        if not is_free:
            await self._validate_gateway_availability(data.gateway_type)

        async with self._uow:
            # rechecked under the per-user lock, counting orders not yet
            # provisioned, so concurrent checkouts can't all pass the reads above
            await self._eligibility.lock_user(actor.id)
            open_orders = await self._transaction_repository.count_open_new_orders(
                actor.id, datetime_now()
            )
            if not await self._eligibility.is_purchasable(
                plan, user, has_open_order=open_orders > 0
            ) or not _link_code_matches(plan, data.plan_code):
                raise NotFoundError(
                    f"Plan '{data.plan_id}' not found", code=ErrorCode.PLAN_NOT_FOUND
                )
            if data.purchase_type is PurchaseType.NEW:
                await self._eligibility.assert_below_cap(actor.id, lock=True, pending=open_orders)
            # the one-shot discount is spent in the same transaction as the
            # order, so a racing checkout finds it gone and re-quotes
            await self._spend_purchase_discount(quote, user)
            order = await self._create_order(actor.id, data, plan, quote, customer_email)

            if is_free:
                order = await self._transaction_repository.mark_status(
                    order.id, TransactionStatus.PAID
                )
                await self._uow.after_commit(
                    partial(dispatch_fulfillment, self._purchase_dispatch, order)
                )
                return CheckoutResultDto(order_id=order.id, confirmation_url=None)

        gateway = self._gateway_factory.build(data.gateway_type, gateway_settings)
        try:
            intent = await gateway.create_payment(order)
        except Exception as error:
            # no payment exists at the provider, so the order and its spent discount go back
            async with self._uow:
                failed = await self._transaction_repository.mark_status_if(
                    order.id,
                    TransactionStatus.FAILED,
                    current=frozenset({TransactionStatus.PENDING}),
                )
                if failed and order.discount_source is DiscountSource.PURCHASE:
                    await self._user_repository.restore_purchase_discount(
                        order.user_id,
                        order.discount_percent,
                        order.discount_promocode_id,
                        from_promocode=order.discount_from_promocode,
                    )
            if isinstance(error, PaymentGatewayError):
                raise
            raise PaymentGatewayError(f"Provider request failed: {type(error).__name__}") from error

        async with self._uow:
            await self._transaction_repository.mark_status(
                order.id,
                TransactionStatus.PENDING,
                external_payment_id=intent.provider_payment_id,
            )

        return CheckoutResultDto(order_id=order.id, confirmation_url=intent.confirmation_url)

    async def _load_gateway_settings(self, data: CreateCheckoutDto) -> dict[str, str]:
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
        gateway_settings = await self._gateway_repository.get_raw_settings(data.gateway_type)
        if data.currency is not gateway_currency(data.gateway_type, gateway_settings):
            raise ValidationError(
                f"Gateway '{data.gateway_type.value}' does not settle '{data.currency.value}'",
                code=ErrorCode.GATEWAY_CURRENCY_UNSUPPORTED,
            )
        return gateway_settings

    async def _load_purchasable_plan(
        self, user_id: int, data: CreateCheckoutDto
    ) -> tuple[PlanDto, UserDto]:
        plan = await self._plan_repository.get_by_id(data.plan_id)
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User '{user_id}' not found", code=ErrorCode.USER_NOT_FOUND)

        if not await self._eligibility.is_purchasable(plan, user) or not _link_code_matches(
            plan, data.plan_code
        ):
            # Same answer as a missing plan: a distinct one would let anyone
            # walk plan ids and learn which hidden plans exist.
            raise NotFoundError(f"Plan '{data.plan_id}' not found", code=ErrorCode.PLAN_NOT_FOUND)
        return plan, user

    async def _create_order(
        self,
        user_id: int,
        data: CreateCheckoutDto,
        plan: PlanDto,
        quote: PriceQuote,
        customer_email: Optional[str],
    ) -> TransactionDto:
        return await self._transaction_repository.create(
            CreateTransactionDto(
                user_id=user_id,
                plan_id=data.plan_id,
                plan_snapshot=PlanSnapshot.from_plan(
                    plan,
                    price_paid=quote.final_price,
                    currency=data.currency,
                    duration_days=data.duration_days,
                ),
                duration_days=data.duration_days,
                currency=data.currency,
                purchase_type=data.purchase_type,
                target_subscription_id=data.target_subscription_id,
                gateway_type=data.gateway_type,
                base_price=quote.base_price,
                discount_percent=quote.discount_percent,
                discount_source=quote.discount_source,
                plan_discount_percent=quote.plan_discount_percent,
                final_price=quote.final_price,
                anchor_base_price=quote.anchor_base_price,
                anchor_final_price=quote.anchor_final_price,
                discount_promocode_id=quote.discount_promocode_id,
                discount_from_promocode=(
                    quote.discount_promocode_id is not None
                    and quote.discount_source is DiscountSource.PURCHASE
                ),
                customer_email=customer_email,
                idempotency_key=uuid4().hex,
                expires_at=datetime_now() + _ORDER_TTL,
            )
        )

    async def _drop_dead_promocode_discounts(self, user: UserDto) -> UserDto:
        sources = {
            source
            for source in (user.personal_discount_promocode_id, user.purchase_discount_promocode_id)
            if source is not None
        }
        if not sources:
            return user
        async with self._uow:
            dead = {
                source for source in sources if not await self._promocode_liveness.is_live(source)
            }
            if not dead:
                return user
            await self._user_repository.clear_discounts_from(dead, user_id=user.id)
            refreshed = await self._user_repository.get_by_id(user.id)
        if refreshed is None:
            raise NotFoundError(f"User '{user.id}' not found", code=ErrorCode.USER_NOT_FOUND)
        logger.info(f"{user.log} Dropped discounts from ended promocodes {sorted(dead)}")
        return refreshed

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
            gateway_config = await self._gateway_repository.get_by_type(gateway_type)
            if not gateway_config.is_active or not gateway_config.is_configured:
                raise ValidationError(
                    f"Gateway '{gateway_type.value}' is not available",
                    code=ErrorCode.GATEWAY_NOT_AVAILABLE,
                )

    async def _validate_provisioning_preconditions(
        self, user_id: int, data: CreateCheckoutDto
    ) -> None:
        # PurchaseSubscriptionUseCase re-checks the target subscription under
        # its own lock. A paid order is provisioned even if the cap filled up
        # meanwhile; only a free one is refused at fulfilment.
        async with self._uow:
            if data.purchase_type is PurchaseType.NEW:
                if data.target_subscription_id is not None:
                    raise ValidationError(
                        "target_subscription_id is forbidden for a NEW purchase",
                        code=ErrorCode.TARGET_SUBSCRIPTION_FORBIDDEN,
                    )
                await self._eligibility.assert_below_cap(user_id)
                return

        await self._validate_target_subscription(user_id, data)

    async def _validate_target_subscription(self, user_id: int, data: CreateCheckoutDto) -> None:
        async with self._uow:
            if data.target_subscription_id is None:
                raise ValidationError(
                    f"target_subscription_id is required for a {data.purchase_type.value}",
                    code=ErrorCode.TARGET_SUBSCRIPTION_REQUIRED,
                )

            target = await get_owned_target(
                self._subscription_repository, data.target_subscription_id, user_id
            )
            if target.status is SubscriptionStatus.DELETED:
                raise ValidationError(
                    f"Cannot {data.purchase_type.value.lower()} a deleted subscription",
                    code=ErrorCode.SUBSCRIPTION_DELETED,
                )
            if target.status is SubscriptionStatus.DISABLED:
                raise ValidationError(
                    f"Cannot {data.purchase_type.value.lower()} a disabled subscription",
                    code=ErrorCode.SUBSCRIPTION_DISABLED,
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
