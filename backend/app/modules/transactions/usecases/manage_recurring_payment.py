from datetime import datetime, timedelta

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PurchaseChannel
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.subscriptions import SubscriptionRepository, get_manageable_subscription
from app.modules.transactions.events import RecurringPaymentManagedEvent
from app.modules.transactions.recurring_admin import ManageRecurringPaymentDto
from app.modules.transactions.recurring_dto import RecurringPaymentDto
from app.modules.transactions.recurring_policy import RecurringReason, RetryKind, recurring_reason
from app.modules.transactions.recurring_repository import RecurringPaymentRepository
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases.process_recurring_payments import (
    ProcessRecurringPaymentsUseCase,
)
from app.modules.users import UserRepository


class ManageRecurringPaymentUseCase(UseCase[ManageRecurringPaymentDto, None]):
    required_permission = Permission.TRANSACTIONS_RECURRING_MANAGE

    def __init__(
        self,
        recurring_repository: RecurringPaymentRepository,
        transaction_repository: TransactionRepository,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        worker: ProcessRecurringPaymentsUseCase,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._recurring = recurring_repository
        self._transactions = transaction_repository
        self._subscriptions = subscription_repository
        self._users = user_repository
        self._worker = worker
        self._events = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: ManageRecurringPaymentDto) -> None:
        async with self._uow:
            subscription = await get_manageable_subscription(
                self._subscriptions, self._users, actor, data.subscription_id
            )
            target = await self._users.find_by_id(subscription.user_id)
            before = await self._recurring.get(data.subscription_id)
            if before is None or target is None:
                raise ConflictError(
                    "No recurring payment is available", code=ErrorCode.GATEWAY_NOT_AVAILABLE
                )
            if before.pending_transaction_id != data.expected_pending_transaction_id:
                raise ConflictError(
                    "The pending payment changed", code=ErrorCode.PAYMENT_ORDER_NOT_CHECKABLE
                )
            if before.pending_transaction_id is not None:
                await self._transactions.get_by_id_for_update(before.pending_transaction_id)
            mandate = await self._recurring.get(data.subscription_id, for_update=True)
            if mandate is None or mandate.pending_transaction_id != before.pending_transaction_id:
                raise ConflictError(
                    "The pending payment changed", code=ErrorCode.PAYMENT_ORDER_NOT_CHECKABLE
                )
            if data.action == "retry":
                await self._retry(mandate, subscription.expire_at)
            elif mandate.pending_transaction_id is None:
                raise ConflictError(
                    "There is no pending payment", code=ErrorCode.PAYMENT_ORDER_NOT_CHECKABLE
                )
            elif data.action == "close":
                await self._close(actor, data, mandate)
            await self._events.publish(
                RecurringPaymentManagedEvent(
                    actor=actor,
                    target=target,
                    subscription_id=data.subscription_id,
                    action=data.action,
                    order_id=before.pending_transaction_id,
                    previous_reason=before.last_error,
                    ip_address=data.client_ip,
                )
            )
        if data.action == "check" and before.pending_transaction_id is not None:
            await self._worker.check_pending(data.subscription_id, before.pending_transaction_id)

    async def _retry(self, mandate: RecurringPaymentDto, expire_at: datetime) -> None:
        terms = await self._recurring.consent_terms(mandate.consent_id)
        reason = recurring_reason(mandate.last_error)
        if (
            reason is None
            or not (
                reason.policy.retry is RetryKind.TECHNICAL
                or reason is RecurringReason.PROVIDER_CONFIGURATION_ERROR
            )
            or mandate.customer_disabled
            or mandate.pending_transaction_id is not None
            or mandate.submitted_at is not None
            or not mandate.payment_method_id
            or terms is None
            or expire_at < datetime_now() - timedelta(hours=terms.max_overdue_hours)
        ):
            raise ValidationError(
                "Renewal cannot be retried under the current consent",
                code=ErrorCode.GATEWAY_NOT_AVAILABLE,
            )
        await self._recurring.resume(mandate.subscription_id)

    async def _close(
        self, actor: Actor, data: ManageRecurringPaymentDto, mandate: RecurringPaymentDto
    ) -> None:
        if not await self._recurring.retire_pending(
            data.subscription_id,
            mandate.pending_transaction_id,
            force_unknown=True,
            notify=False,
        ):
            raise ConflictError(
                "The payment can no longer be closed", code=ErrorCode.PAYMENT_ORDER_NOT_CHECKABLE
            )
        await self._recurring.revoke_consent(
            data.subscription_id,
            channel=PurchaseChannel.CABINET,
            event_id=f"admin:{actor.id}",
            ip_address=data.client_ip,
        )
        await self._recurring.disable(data.subscription_id, RecurringReason.ADMIN_CLOSED)
