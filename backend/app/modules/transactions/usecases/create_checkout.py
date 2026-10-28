from datetime import timedelta
from functools import partial
from typing import Final, Optional
from uuid import uuid4

from loguru import logger

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    DiscountSource,
    LegalAcceptanceTrigger,
    LegalDocumentKind,
    PaymentGatewayType,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PaymentGatewayError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.gateways import REQUIRE_PAID_PURCHASE_FIELD_KEY, GatewayRepository, gateway_flags
from app.modules.legal import LegalAcceptanceRecorder
from app.modules.plans import PlanDto
from app.modules.settings import GetAccessSettingsUseCase, SettingsRepository
from app.modules.subscriptions import (
    PlanSnapshot,
    PurchaseEligibility,
    PurchaseSubscriptionDispatch,
    SubscriptionRepository,
    get_owned_target,
)
from app.modules.transactions.checkout_pricing import CheckoutPricer, link_code_matches
from app.modules.transactions.dto import (
    CheckoutResultDto,
    CreateCheckoutDto,
    CreateTransactionDto,
    PriceQuote,
    TransactionDto,
)
from app.modules.transactions.events import CheckoutCreatedEvent
from app.modules.transactions.fulfillment import dispatch_fulfillment
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.gateways.registry import GATEWAY_REGISTRY, gateway_currency
from app.modules.transactions.gateways.telegram_stars import with_bot_settings
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.unpaid_orders import give_back_purchase_discount
from app.modules.transactions.waitlist_repository import WaitlistRepository
from app.modules.users import UserDto, UserRepository

_ORDER_TTL: Final[timedelta] = timedelta(minutes=30)


class CreateCheckoutUseCase(UseCase[CreateCheckoutDto, CheckoutResultDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        pricer: CheckoutPricer,
        user_repository: UserRepository,
        gateway_repository: GatewayRepository,
        transaction_repository: TransactionRepository,
        subscription_repository: SubscriptionRepository,
        eligibility: PurchaseEligibility,
        uow: UnitOfWork,
        gateway_factory: PaymentGatewayFactory,
        purchase_dispatch: PurchaseSubscriptionDispatch,
        get_access_settings_use_case: GetAccessSettingsUseCase,
        waitlist_repository: WaitlistRepository,
        settings_repository: SettingsRepository,
        config: AppConfig,
        event_publisher: EventPublisher,
        legal_recorder: LegalAcceptanceRecorder,
    ) -> None:
        self._pricer = pricer
        self._user_repository = user_repository
        self._gateway_repository = gateway_repository
        self._transaction_repository = transaction_repository
        self._subscription_repository = subscription_repository
        self._eligibility = eligibility
        self._uow = uow
        self._gateway_factory = gateway_factory
        self._purchase_dispatch = purchase_dispatch
        self._get_access_settings_use_case = get_access_settings_use_case
        self._waitlist_repository = waitlist_repository
        self._settings_repository = settings_repository
        self._config = config
        self._event_publisher = event_publisher
        self._legal_recorder = legal_recorder

    def _return_url(self, data: CreateCheckoutDto, order_id: int) -> Optional[str]:
        cabinet_url = self._config.cabinet.url
        if data.return_to != "cabinet" or not cabinet_url:
            return None
        return f"{cabinet_url}/payment/result?order_id={order_id}"

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

    async def _reserve_trial(self, user_id: int, *, is_free: bool) -> None:
        """One trial per customer, held under the per-user lock: the flag itself is
        spent on delivery, so a second trial order or the trial button racing this
        checkout would each deliver one."""
        if is_free:
            # delivered right away: spent here, the trial button then finds it gone
            taken = not await self._user_repository.spend_trial(user_id)
        else:
            taken = (
                await self._transaction_repository.count_open_new_orders(
                    user_id, datetime_now(), trial_only=True
                )
                > 0
            )
        if taken:
            raise ValidationError(
                f"Trial is not available for user '{user_id}'", code=ErrorCode.TRIAL_NOT_AVAILABLE
            )

    async def _execute(self, actor: UserDto, data: CreateCheckoutDto) -> CheckoutResultDto:
        if not (await self._get_access_settings_use_case.system()).payments_enabled:
            # own transaction, so the refusal below doesn't roll it back
            async with self._uow:
                await self._waitlist_repository.add(actor.id)
            raise PermissionDeniedError("Payments are disabled", code=ErrorCode.PAYMENTS_DISABLED)

        async with self._uow:
            gateway_settings = await self._load_gateway_settings(actor.id, data)
            plan, user = await self._pricer.load_purchasable_plan(
                actor.id,
                data.plan_id,
                data.plan_code,
                data.target_subscription_id if data.purchase_type is PurchaseType.RENEW else None,
            )
            customer_email = self._resolve_customer_email(data, user, gateway_settings)

        await self._validate_provisioning_preconditions(actor.id, data)
        user = await self._pricer.drop_dead_promocode_discounts(user)
        quote = await self._pricer.quote(plan, data.duration_days, data.currency, user)
        if data.expected_price is not None and quote.final_price != data.expected_price:
            raise ConflictError(
                f"Price changed from {data.expected_price} to {quote.final_price}",
                code=ErrorCode.PRICE_CHANGED,
            )

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
            if data.purchase_type is not PurchaseType.RENEW and (
                not await self._eligibility.is_purchasable(
                    plan, user, has_open_order=open_orders > 0
                )
                or not link_code_matches(plan, data.plan_code)
            ):
                raise NotFoundError(
                    f"Plan '{data.plan_id}' not found", code=ErrorCode.PLAN_NOT_FOUND
                )
            if plan.is_trial:
                await self._reserve_trial(actor.id, is_free=is_free)
            if data.purchase_type is PurchaseType.NEW:
                await self._eligibility.assert_below_cap(actor.id, lock=True, pending=open_orders)
            # the one-shot discount is spent in the same transaction as the
            # order, so a racing checkout finds it gone and re-quotes
            await self._spend_purchase_discount(quote, user)
            order = await self._create_order(actor.id, data, plan, quote, customer_email)
            # paying accepts the offer on either channel; the client's locale only picks
            # the revision, the customer's language when it sends none
            await self._legal_recorder.record(
                user_id=actor.id,
                channel=data.channel,
                trigger=LegalAcceptanceTrigger.PAYMENT,
                locale=data.legal_locale or user.language,
                kinds=frozenset(LegalDocumentKind),
                transaction_id=order.id,
                ip_address=data.client_ip,
            )
            await self._event_publisher.publish(
                CheckoutCreatedEvent(
                    user=actor,
                    order_id=order.id,
                    gateway_type=order.gateway_type,
                    amount=str(order.final_price),
                    currency=order.currency,
                )
            )

            if is_free:
                order = await self._transaction_repository.mark_status(
                    order.id, TransactionStatus.PAID
                )
                await self._uow.after_commit(
                    partial(dispatch_fulfillment, self._purchase_dispatch, order)
                )
                return CheckoutResultDto(order_id=order.id, confirmation_url=None)

        gateway = self._gateway_factory.build(
            data.gateway_type, gateway_settings, self._return_url(data, order.id)
        )
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
                if failed:
                    await give_back_purchase_discount(self._user_repository, order)
            # the provider's answer stays in the log: it can name the merchant
            # account or the request, which is not the customer's business
            logger.exception(
                f"Gateway '{data.gateway_type}' failed to create a payment for order {order.id}"
            )
            code = (
                error.code
                if isinstance(error, PaymentGatewayError)
                else ErrorCode.PAYMENT_GATEWAY_ERROR
            )
            raise PaymentGatewayError("The payment provider is unavailable", code=code) from error

        async with self._uow:
            # a webhook that beat us here has stored the payment id and marked it PAID already
            await self._transaction_repository.mark_status_if(
                order.id,
                TransactionStatus.PENDING,
                current=frozenset({TransactionStatus.PENDING}),
                external_payment_id=intent.provider_payment_id,
            )

        return CheckoutResultDto(order_id=order.id, confirmation_url=intent.confirmation_url)

    async def _load_gateway_settings(self, user_id: int, data: CreateCheckoutDto) -> dict[str, str]:
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
        if data.gateway_type is PaymentGatewayType.TELEGRAM_STARS:
            bot_settings = await self._settings_repository.get_bot_settings()
            # without the webhook the bot never sees pre_checkout_query, so the link is dead
            if not bot_settings.is_configured or bot_settings.token is None:
                raise ValidationError(
                    "The bot is not configured", code=ErrorCode.GATEWAY_NOT_AVAILABLE
                )
            if gateway_flags(data.gateway_type, gateway_settings).get(
                REQUIRE_PAID_PURCHASE_FIELD_KEY, False
            ) and not await self._transaction_repository.has_paid_purchase(user_id):
                raise ValidationError(
                    "Telegram Stars needs a paid purchase first",
                    code=ErrorCode.GATEWAY_NOT_AVAILABLE,
                )
            gateway_settings = with_bot_settings(
                gateway_settings, bot_settings.token.get_secret_value(), bot_settings.proxy
            )
        return gateway_settings

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
                channel=data.channel,
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
            # a NEW purchase replaces the trial and keeps its connection link
            if target.is_trial:
                raise ValidationError(
                    f"Cannot {data.purchase_type.value.lower()} a trial",
                    code=ErrorCode.TRIAL_NOT_RENEWABLE,
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
