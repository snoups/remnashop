from functools import partial
from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import DiscountSource, TransactionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, PaymentGatewayError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways import GatewayRepository
from app.modules.subscriptions import PurchaseSubscriptionDispatch
from app.modules.transactions.dto import CheckTransactionPaymentDto, PaymentCheckResultDto
from app.modules.transactions.events import TransactionPaymentConfirmedEvent
from app.modules.transactions.fulfillment import dispatch_fulfillment
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.unpaid_orders import UNPAID_FINAL
from app.modules.transactions.visibility import visible_transaction
from app.modules.users import UserRepository

_CHECKABLE: Final[frozenset[TransactionStatus]] = UNPAID_FINAL | {TransactionStatus.PENDING}


class CheckTransactionPaymentUseCase(UseCase[CheckTransactionPaymentDto, PaymentCheckResultDto]):
    required_permission = Permission.TRANSACTIONS_PAYMENT_CHECK

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        gateway_repository: GatewayRepository,
        gateway_factory: PaymentGatewayFactory,
        user_repository: UserRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
        purchase_dispatch: PurchaseSubscriptionDispatch,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._gateway_repository = gateway_repository
        self._gateway_factory = gateway_factory
        self._user_repository = user_repository
        self._event_publisher = event_publisher
        self._uow = uow
        self._purchase_dispatch = purchase_dispatch

    async def _execute(
        self, actor: Actor, data: CheckTransactionPaymentDto
    ) -> PaymentCheckResultDto:
        async with self._uow:
            order = await self._transaction_repository.get_by_id(data.transaction_id)
            user = await self._user_repository.find_by_id(order.user_id)
            settings = await self._gateway_repository.get_raw_settings(order.gateway_type)
        gateway = self._gateway_factory.build(order.gateway_type, settings)
        if (
            order.status not in _CHECKABLE
            or not gateway.supports_status_check
            or user is None
            or user.deleted_at is not None
        ):
            raise ConflictError(
                f"Transaction '{order.id}' can't be checked with its gateway",
                code=ErrorCode.PAYMENT_ORDER_NOT_CHECKABLE,
            )

        try:
            payment = await gateway.check_payment(order)
        except PaymentGatewayError:
            raise
        except Exception as error:  # any provider API failure is a gateway problem
            raise PaymentGatewayError("Could not check payment") from error

        if payment is not None:
            async with self._uow:
                # a webhook may have settled it while the provider was asked
                current = await self._transaction_repository.get_by_id_for_update(order.id)
                if current.status in _CHECKABLE:
                    await self._transaction_repository.mark_status_if(
                        current.id,
                        TransactionStatus.PAID,
                        current=frozenset({current.status}),
                        external_payment_id=payment.provider_payment_id,
                    )
                    await self._transaction_repository.remember_payment_method(
                        current.id, payment.saved_payment_method_id, payment.payment_method_shop_id
                    )
                    if (
                        current.status in UNPAID_FINAL
                        and current.discount_source is DiscountSource.PURCHASE
                    ):
                        # handed back on cancel; a no-op once spent elsewhere
                        await self._user_repository.spend_purchase_discount(
                            current.user_id, current.discount_percent
                        )
                    await self._event_publisher.publish(
                        TransactionPaymentConfirmedEvent(
                            actor=actor,
                            target=user,
                            order_id=current.id,
                            previous_status=current.status,
                            gateway_type=current.gateway_type,
                            ip_address=data.client_ip,
                        )
                    )
                    if not current.is_test:
                        await self._uow.after_commit(
                            partial(dispatch_fulfillment, self._purchase_dispatch, current)
                        )
                    logger.info(
                        f"{actor.log} Confirmed payment of transaction '{current.id}' "
                        f"({current.status.value}) with {current.gateway_type.value}"
                    )

        async with self._uow:
            order = await self._transaction_repository.get_by_id(data.transaction_id)
        return PaymentCheckResultDto(
            transaction=visible_transaction(actor, order, user), paid=payment is not None
        )
