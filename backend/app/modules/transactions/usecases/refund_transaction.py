from typing import Final, Optional, cast

from loguru import logger
from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType, TransactionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, PaymentGatewayError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.lock import cron_lock
from app.modules.gateways import GatewayRepository
from app.modules.settings import SettingsRepository
from app.modules.subscriptions import PurchaseRollbackDto, PurchaseRollbackService
from app.modules.transactions.dto import RefundResultDto, RefundTransactionDto, TransactionDto
from app.modules.transactions.events import (
    TransactionRefundedEvent,
    TransactionRefundedManuallyEvent,
)
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.gateways.telegram_stars import (
    TelegramStarsGateway,
    with_bot_settings,
)
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases._refund import refund_refusal, rollback_input
from app.modules.transactions.visibility import visible_transaction
from app.modules.users import UserDto, UserRepository

_LOCK_TTL_S: Final[int] = 60


def _not_refundable(order_id: int, reason: str) -> ConflictError:
    return ConflictError(
        f"Transaction '{order_id}' can't be refunded: {reason}",
        code=ErrorCode.TRANSACTION_NOT_REFUNDABLE,
    )


class RefundTransactionUseCase(UseCase[RefundTransactionDto, RefundResultDto]):
    required_permission = Permission.TRANSACTIONS_REFUND

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        user_repository: UserRepository,
        gateway_repository: GatewayRepository,
        settings_repository: SettingsRepository,
        gateway_factory: PaymentGatewayFactory,
        purchase_rollback_service: PurchaseRollbackService,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
        redis: Redis,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._user_repository = user_repository
        self._gateway_repository = gateway_repository
        self._settings_repository = settings_repository
        self._gateway_factory = gateway_factory
        self._purchase_rollback_service = purchase_rollback_service
        self._event_publisher = event_publisher
        self._uow = uow
        self._redis = redis

    async def _execute(self, actor: Actor, data: RefundTransactionDto) -> RefundResultDto:
        rollback: Optional[PurchaseRollbackDto] = None
        # the row lock ends with the first transaction; this keeps a second click
        # from reaching Telegram while the first is still on its way
        async with cron_lock(
            self._redis, f"refund:{data.transaction_id}", ttl_seconds=_LOCK_TTL_S
        ) as acquired:
            if not acquired:
                raise _not_refundable(data.transaction_id, "already in progress")

            async with self._uow:
                order = await self._transaction_repository.get_by_id_for_update(data.transaction_id)
                payer = await self._user_repository.find_by_id(order.user_id)
                bot_settings = await self._settings_repository.get_bot_settings()
                token = bot_settings.token
                reason = refund_refusal(order, payer, token is not None)
                charge_id = order.external_payment_id
                if reason is not None or payer is None or payer.telegram_id is None:
                    raise _not_refundable(order.id, reason or "no_telegram_id")
                if charge_id is None:
                    raise _not_refundable(order.id, "no_charge_id")
                if token is None:
                    raise _not_refundable(order.id, "bot_not_configured")
                if data.rollback_subscription:
                    rollback = await rollback_input(self._transaction_repository, order)
                gateway_settings = with_bot_settings(
                    await self._gateway_repository.get_raw_settings(
                        PaymentGatewayType.TELEGRAM_STARS
                    ),
                    token.get_secret_value(),
                    bot_settings.proxy,
                )

            if rollback is not None:
                await self._assert_rollback_available(rollback)
            await self._refund_in_telegram(order.id, gateway_settings, charge_id, payer.telegram_id)
            await self._record(actor, data, order, payer, charge_id)

        rollback_failed = False
        if rollback is not None:
            # an order paid while Telegram was answering changes what may be rolled back
            async with self._uow:
                rollback = await rollback_input(self._transaction_repository, order)
            rollback_failed = not await self._roll_back(actor, order.id, rollback)
        async with self._uow:
            order = await self._transaction_repository.get_by_id(order.id)
        return RefundResultDto(
            transaction=visible_transaction(actor, order, payer), rollback_failed=rollback_failed
        )

    async def _assert_rollback_available(self, rollback: PurchaseRollbackDto) -> None:
        preview = await self._purchase_rollback_service.preview(rollback)
        if not preview.available:
            raise ConflictError(
                f"Purchase rollback is blocked: {preview.blocked_reason}",
                code=ErrorCode.SUBSCRIPTION_ROLLBACK_BLOCKED,
            )

    async def _refund_in_telegram(
        self, order_id: int, gateway_settings: dict[str, str], charge_id: str, telegram_id: int
    ) -> None:
        gateway = cast(
            TelegramStarsGateway,
            self._gateway_factory.build(PaymentGatewayType.TELEGRAM_STARS, gateway_settings),
        )
        try:
            await gateway.refund(charge_id, telegram_id)
        except PaymentGatewayError:
            raise
        except Exception as error:
            # raw transport errors may carry the tokened URL
            logger.error(
                f"Order '{order_id}' refund outcome unknown (charge '{charge_id}'): "
                f"{type(error).__name__} -- retry the refund; Telegram reports an already "
                f"refunded charge as done"
            )
            raise PaymentGatewayError(f"Provider request failed: {type(error).__name__}") from error

    async def _record(
        self,
        actor: Actor,
        data: RefundTransactionDto,
        order: TransactionDto,
        payer: UserDto,
        charge_id: str,
    ) -> None:
        try:
            async with self._uow:
                changed = await self._transaction_repository.mark_status_if(
                    order.id,
                    TransactionStatus.REFUNDED,
                    current=frozenset({TransactionStatus.PAID}),
                )
                if changed:
                    await self._event_publisher.publish(
                        TransactionRefundedEvent(
                            order_id=order.id,
                            user_id=order.user_id,
                            payment_key=order.idempotency_key,
                            gateway_type=order.gateway_type.value,
                            amount=str(order.final_price),
                            currency=order.currency.value,
                        )
                    )
                    await self._event_publisher.publish(
                        TransactionRefundedManuallyEvent(
                            actor=actor,
                            target=payer,
                            order_id=order.id,
                            rollback_subscription=data.rollback_subscription,
                            ip_address=data.client_ip,
                        )
                    )
        except Exception:
            logger.error(
                f"Order '{order.id}' refunded in Telegram (charge '{charge_id}') "
                f"but not recorded -- mark it manually"
            )
            raise
        if not changed:
            logger.error(
                f"Order '{order.id}' refunded in Telegram (charge '{charge_id}') "
                f"but its status moved meanwhile"
            )
            raise _not_refundable(order.id, "status changed")
        logger.info(f"{actor.log} Refunded transaction '{order.id}' in Telegram Stars")

    async def _roll_back(self, actor: Actor, order_id: int, rollback: PurchaseRollbackDto) -> bool:
        try:
            await self._purchase_rollback_service.rollback(actor, rollback)
        except Exception:
            logger.exception(f"{actor.log} Rollback after refunding '{order_id}' failed")
            return False
        return True
