import uuid
from decimal import Decimal
from typing import Optional
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from pydantic import SecretStr
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.encryption import decrypt, encrypt
from src.core.enums import (
    Currency,
    Locale,
    PaymentGatewayType,
    SystemNotificationType,
    TransactionStatus,
)
from src.core.storage_keys import DefaultCurrencyKey
from src.core.utils.formatters import i18n_format_days_to_duration
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import (
    AnyGatewaySettingsDto,
    PaymentGatewayDto,
    PlanSnapshotDto,
    SubscriptionDto,
    TransactionDto,
    UserDto,
)
from src.infrastructure.payment_gateways import BasePaymentGateway, PaymentGatewayFactory
from src.infrastructure.redis import RedisRepository
from src.infrastructure.taskiq.tasks.notifications import send_system_notification_task
from src.infrastructure.taskiq.tasks.redirects import redirect_to_main_menu_task
from src.services.subscription import SubscriptionService

from .base import BaseService
from .transaction import TransactionService


# TODO: Make payment gateway sorting customizable for display
class PaymentGatewayService(BaseService):
    uow: UnitOfWork
    transaction_service: TransactionService
    payment_gateway_factory: PaymentGatewayFactory

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
        transaction_service: TransactionService,
        subscription_service: SubscriptionService,
        payment_gateway_factory: PaymentGatewayFactory,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow
        self.transaction_service = transaction_service
        self.subscription_service = subscription_service
        self.payment_gateway_factory = payment_gateway_factory

    async def get(self, gateway_id: int) -> Optional[PaymentGatewayDto]:
        db_gateway = await self.uow.repository.gateways.get(gateway_id)
        return self._decrypt_gateway_key(PaymentGatewayDto.from_model(db_gateway))

    async def get_by_type(self, gateway_type: PaymentGatewayType) -> Optional[PaymentGatewayDto]:
        db_gateway = await self.uow.repository.gateways.get_by_type(gateway_type)
        return self._decrypt_gateway_key(PaymentGatewayDto.from_model(db_gateway))

    async def get_all(self) -> list[PaymentGatewayDto]:
        db_gateways = await self.uow.repository.gateways.get_all()
        return PaymentGatewayDto.from_model_list(db_gateways)  # NOTE: NOT DECRYPT

    async def update(self, gateway: PaymentGatewayDto) -> Optional[PaymentGatewayDto]:
        updated_data = gateway.changed_data

        if gateway.settings and gateway.settings.changed_data:
            encrypted_settings = self._encrypt_gateway_key(gateway.settings)
            updated_data["settings"] = encrypted_settings.model_dump(by_alias=True)

        db_updated_gateway = await self.uow.repository.gateways.update(
            gateway_id=gateway.id,
            **updated_data,
        )

        return self._decrypt_gateway_key(PaymentGatewayDto.from_model(db_updated_gateway))

    async def filter_active(self, is_active: bool = True) -> list[PaymentGatewayDto]:
        db_gateways = await self.uow.repository.gateways.filter_active(is_active)
        return PaymentGatewayDto.from_model_list(db_gateways)  # NOTE: NOT DECRYPT

    #

    async def create_payment(
        self,
        user: UserDto,
        plan: PlanSnapshotDto,
        price: Decimal,
        gateway_type: PaymentGatewayType,
    ) -> str:
        gateway_instance = await self._get_gateway_instance(gateway_type)

        i18n = self.translator_hub.get_translator_by_locale(locale=user.language)
        details = i18n.get(
            "payment-invoice-description",
            name=plan.name,
            traffic=plan.traffic_limit,
            devices=plan.device_limit,
            duration=plan.duration,
        )
        payment_id = uuid.uuid4()

        transaction = TransactionDto(
            payment_id=payment_id,
            status=TransactionStatus.PENDING,
            gateway=gateway_instance.gateway.type,
            amount=price,
            currency=gateway_instance.gateway.currency,
            plan=plan,
        )
        await self.transaction_service.create(user, transaction)

        pay_url = await gateway_instance.handle_create_payment(
            payment_id=str(payment_id),
            amount=price,
            details=details,
        )
        logger.info(f"Payment link created for user '{user.telegram_id}': '{pay_url}'")
        return pay_url

    async def create_test_payment(self, gateway_type: PaymentGatewayType) -> str:
        gateway_instance = await self._get_gateway_instance(gateway_type)

        test_user = UserDto(
            telegram_id=0,
            name="test_user",
            language=Locale.EN,
        )
        test_price = Decimal("1")
        i18n = self.translator_hub.get_translator_by_locale(locale=test_user.language)
        test_details = i18n.get("test-payment")
        payment_id = "test:" + str(uuid.uuid4())

        return await gateway_instance.handle_create_payment(
            payment_id=payment_id,
            amount=test_price,
            details=test_details,
        )

    async def handle_payment_succeeded(self, payment_id: UUID) -> None:
        transaction = await self.transaction_service.get(payment_id)

        if not transaction or not transaction.user:
            logger.critical("")
            return

        logger.info(f"Payment succeeded '{payment_id}' from '{transaction.user.telegram_id}'")

        transaction.status = TransactionStatus.COMPLETED
        await self.transaction_service.update(transaction)

        # TODO: refferal
        # TODO: split notifications on types
        i18n_key = "ntf-event-subscription-purchase"

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.SUBSCRIPTION,
            i18n_key=i18n_key,
            i18n_kwargs={
                "payment_id": transaction.payment_id,
                "gateway_type": transaction.gateway,
                "payment_amount": transaction.amount.normalize(),
                "currency": transaction.currency.symbol,
                "user_id": str(transaction.user.telegram_id),
                "user_name": transaction.user.name,
                "user_username": transaction.user.username or False,
                "plan_name": transaction.plan.name,
                "plan_type": transaction.plan.type,
                "plan_traffic_limit": transaction.plan.traffic_limit,
                "plan_device_limit": transaction.plan.device_limit,
                "plan_duration": i18n_format_days_to_duration(transaction.plan.duration),
            },
        )
        await redirect_to_main_menu_task.kiq(transaction.user)

        # TODO: subscription remnawave

        # subscription = SubscriptionDto(plan=transaction.plan)

        # await self.subscription_service.create(subscription)
        await self.subscription_service.create_remnawave(transaction.user, transaction.plan)
        logger.success("Subscription!!!")

    async def handle_payment_canceled(self, payment_id: UUID) -> None:
        pass

    #

    async def get_default_currency(self) -> Currency:
        return await self.redis_repository.get(  # type: ignore[return-value]
            key=DefaultCurrencyKey(),
            validator=Currency,
            default=Currency.RUB,
        )

    async def set_default_currency(self, currency: Currency) -> None:
        await self.redis_repository.set(key=DefaultCurrencyKey(), value=currency)

    #

    async def _get_gateway_instance(self, gateway_type: PaymentGatewayType) -> BasePaymentGateway:
        gateway = await self.get_by_type(gateway_type)

        if not gateway:
            raise ValueError(f"Payment gateway of type '{gateway_type}' not found")

        return self.payment_gateway_factory(gateway)

    def _encrypt_gateway_key(
        self,
        gateway_settings: AnyGatewaySettingsDto,
    ) -> AnyGatewaySettingsDto:
        if gateway_settings.key:
            encrypted_key_str = encrypt(gateway_settings.key.get_secret_value())
            gateway_settings.key = encrypted_key_str  # type: ignore[assignment]
        return gateway_settings

    def _decrypt_gateway_key(
        self,
        gateway_dto: Optional[PaymentGatewayDto],
    ) -> Optional[PaymentGatewayDto]:
        if gateway_dto and gateway_dto.settings and gateway_dto.settings.key:
            decrypted_value = decrypt(gateway_dto.settings.key.get_secret_value())
            gateway_dto.settings.key = SecretStr(decrypted_value)
        return gateway_dto
