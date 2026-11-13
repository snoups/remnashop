from datetime import timedelta
from decimal import Decimal
from typing import Final
from uuid import uuid4

from loguru import logger
from remnapy.enums import TrafficLimitStrategy

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    DiscountSource,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import PaymentGatewayError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.gateways import GatewayRepository
from app.modules.pricing import PricingRepository, convert_for_report
from app.modules.settings import SettingsRepository
from app.modules.subscriptions import PlanSnapshot
from app.modules.transactions.dto import CreateTransactionDto, TestPaymentDto
from app.modules.transactions.events import GatewayTestPaymentCreatedEvent
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.gateways.registry import GATEWAY_REGISTRY, gateway_currency
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserDto

_TEST_AMOUNT: Final[Decimal] = Decimal(2)
_TEST_ORDER_TTL: Final[timedelta] = timedelta(minutes=30)
# stands in for an admin without an email when the gateway wants one for a receipt
_TEST_CUSTOMER_EMAIL: Final[str] = "test@example.com"


class CreateTestPaymentUseCase(UseCase[PaymentGatewayType, TestPaymentDto, UserDto]):
    required_permission = Permission.GATEWAYS_TEST

    def __init__(
        self,
        gateway_repository: GatewayRepository,
        transaction_repository: TransactionRepository,
        pricing_repository: PricingRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        gateway_factory: PaymentGatewayFactory,
        event_publisher: EventPublisher,
    ) -> None:
        self._gateway_repository = gateway_repository
        self._transaction_repository = transaction_repository
        self._pricing_repository = pricing_repository
        self._settings_repository = settings_repository
        self._uow = uow
        self._gateway_factory = gateway_factory
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: PaymentGatewayType) -> TestPaymentDto:
        gateway_class = GATEWAY_REGISTRY.get(data)
        if gateway_class is None or data is PaymentGatewayType.TELEGRAM_STARS:
            raise ValidationError(
                f"Gateway '{data.value}' cannot be tested from the dashboard",
                code=ErrorCode.GATEWAY_NOT_TESTABLE,
            )

        async with self._uow:
            gateway_config = await self._gateway_repository.get_by_type(data)
            if not gateway_config.is_configured:
                raise ValidationError(
                    f"Gateway '{data.value}' is not configured",
                    code=ErrorCode.GATEWAY_NOT_CONFIGURED,
                )
            settings = await self._gateway_repository.get_raw_settings(data)
            shop_settings = await self._settings_repository.get_shop_settings()

        customer_email = shop_settings.payment_email or actor.email
        if customer_email is None and gateway_class.requires_customer_email(settings):
            customer_email = _TEST_CUSTOMER_EMAIL

        currency = gateway_currency(data, settings)
        async with self._uow:
            rates = await self._pricing_repository.get_rate_table()
            anchor_amount = convert_for_report(_TEST_AMOUNT, currency, rates.anchor, rates)
            order = await self._transaction_repository.create(
                CreateTransactionDto(
                    user_id=actor.id,
                    plan_id=None,
                    plan_snapshot=PlanSnapshot(
                        plan_id=0,
                        public_code="test",
                        name="Test payment",
                        price_paid=_TEST_AMOUNT,
                        currency=currency,
                        duration_days=0,
                        traffic_limit=0,
                        device_limit=0,
                        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
                        is_trial=False,
                    ),
                    duration_days=0,
                    currency=currency,
                    purchase_type=PurchaseType.NEW,
                    channel=PurchaseChannel.CABINET,
                    target_subscription_id=None,
                    gateway_type=data,
                    base_price=_TEST_AMOUNT,
                    discount_percent=0,
                    discount_source=DiscountSource.NONE,
                    final_price=_TEST_AMOUNT,
                    anchor_base_price=anchor_amount,
                    anchor_final_price=anchor_amount,
                    customer_email=customer_email,
                    idempotency_key=uuid4().hex,
                    expires_at=datetime_now() + _TEST_ORDER_TTL,
                    is_test=True,
                )
            )

        try:
            intent = await self._gateway_factory.build(data, settings).create_payment(order)
        except PaymentGatewayError:
            logger.exception(f"Test payment failed on gateway '{data.value}'")
            raise
        except Exception as error:  # surfaced to the admin, not a 500
            logger.exception(f"Test payment failed on gateway '{data.value}'")
            raise PaymentGatewayError(f"Provider request failed: {type(error).__name__}") from error

        async with self._uow:
            await self._transaction_repository.mark_status(
                order.id,
                TransactionStatus.PENDING,
                external_payment_id=intent.provider_payment_id,
            )
            await self._event_publisher.publish(
                GatewayTestPaymentCreatedEvent(actor=actor, order_id=order.id, gateway_type=data)
            )
        logger.info(f"{actor.log} Created test transaction '{order.id}' on gateway '{data.value}'")
        return TestPaymentDto(order_id=order.id, confirmation_url=intent.confirmation_url)
