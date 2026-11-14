from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import UpdateUserRequestDto

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PurchaseType, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.pricing import PricingRepository
from app.modules.subscriptions.domain import refunded_unlimited_expiry
from app.modules.subscriptions.dto import (
    PurchaseRollbackDto,
    RollbackPreviewDto,
    SubscriptionDto,
)
from app.modules.subscriptions.eligibility import subscription_owner
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.panel import restore, revert_panel_to_owner
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.revoker import PanelSubscriptionRevoker
from app.modules.users import UserRepository


async def _rollback_blocker(
    repository: SubscriptionRepository, data: PurchaseRollbackDto
) -> Optional[str]:
    if data.fulfilled_subscription_id is None:
        return "not_provisioned"
    fulfilled = await repository.get_by_id(data.fulfilled_subscription_id)
    if data.purchase_type is PurchaseType.CHANGE:
        if data.target_subscription_id is None:
            return "not_provisioned"
        if fulfilled.status is SubscriptionStatus.DELETED:
            return "changed_again"
        if data.has_later_paid_order:
            return "renewed_or_changed_later"
        return None
    if fulfilled.status is SubscriptionStatus.DELETED:
        return "subscription_deleted"
    if data.purchase_type is PurchaseType.NEW and data.has_later_paid_order:
        return "renewed_or_changed_later"
    return None


def _blocked(reason: str) -> ConflictError:
    return ConflictError(
        f"Purchase rollback is blocked: {reason}", code=ErrorCode.SUBSCRIPTION_ROLLBACK_BLOCKED
    )


def _assert_unchanged(locked: SubscriptionDto, read: SubscriptionDto) -> None:
    if locked.status is SubscriptionStatus.DELETED:
        raise _blocked("subscription_deleted")
    if locked.expire_at != read.expire_at:
        raise _blocked("subscription_changed")


class PurchaseRollbackService:
    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        lifecycle_service: SubscriptionLifecycleService,
        revoker: PanelSubscriptionRevoker,
        pricing_repository: PricingRepository,
        remnawave_sdk: RemnawaveSDK,
        idempotency: PurchaseIdempotencyRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._idempotency = idempotency
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._lifecycle_service = lifecycle_service
        self._revoker = revoker
        self._pricing_repository = pricing_repository
        self._remnawave_sdk = remnawave_sdk
        self._event_publisher = event_publisher
        self._uow = uow

    async def _pending_renewal(
        self, data: PurchaseRollbackDto
    ) -> Optional[tuple[SubscriptionDto, datetime]]:
        """A renewal whose worker extended the panel and died before the database
        caught up: the subscription and the expiry pinned for it."""
        if (
            data.purchase_type is not PurchaseType.RENEW
            or data.fulfilled_subscription_id is not None
            or data.target_subscription_id is None
            or data.idempotency_key is None
        ):
            return None
        pinned = await self._idempotency.find_pending_renew_expire_at(data.idempotency_key)
        if pinned is None:
            return None
        target = await self._subscription_repository.get_by_id(data.target_subscription_id)
        if target.status is SubscriptionStatus.DELETED:
            return None
        return target, pinned

    async def preview(self, data: PurchaseRollbackDto) -> RollbackPreviewDto:
        old_term_expired = False
        async with self._uow:
            if await self._pending_renewal(data) is not None:
                return RollbackPreviewDto(
                    available=True, blocked_reason=None, old_term_expired=False
                )
            blocker = await _rollback_blocker(self._subscription_repository, data)
            if data.purchase_type is PurchaseType.CHANGE and data.target_subscription_id:
                old = await self._subscription_repository.get_by_id(data.target_subscription_id)
                old_term_expired = old.expire_at <= datetime_now()
        return RollbackPreviewDto(
            available=blocker is None, blocked_reason=blocker, old_term_expired=old_term_expired
        )

    async def rollback(self, actor: Actor, data: PurchaseRollbackDto) -> None:
        async with self._uow:
            pending = await self._pending_renewal(data)
        if pending is not None:
            await self._undo_pending_renewal(data, *pending)
            return
        old: Optional[SubscriptionDto] = None
        async with self._uow:
            blocker = await _rollback_blocker(self._subscription_repository, data)
            if blocker is not None or data.fulfilled_subscription_id is None:
                raise _blocked(blocker or "not_provisioned")
            fulfilled = await self._subscription_repository.get_by_id(
                data.fulfilled_subscription_id
            )
            if data.purchase_type is PurchaseType.NEW:
                locked = await self._subscription_repository.get_by_id_for_update(fulfilled.id)
                if locked.status is SubscriptionStatus.DELETED:
                    raise _blocked("subscription_deleted")
                await self._revoker.revoke(locked)
                await self._publish(actor, locked)
            elif data.purchase_type is PurchaseType.CHANGE and data.target_subscription_id:
                old = await self._subscription_repository.get_by_id(data.target_subscription_id)

        if data.purchase_type is PurchaseType.RENEW:
            await self._shorten(actor, data, fulfilled)
        elif old is not None:
            await self._restore_replaced(actor, old, fulfilled)
        logger.info(f"{actor.log} Rolled back subscription '{fulfilled.id}' after a refund")

    async def _undo_pending_renewal(
        self, data: PurchaseRollbackDto, target: SubscriptionDto, pinned: datetime
    ) -> None:
        # the database never took this renewal, so only the panel has to give it back
        panel_user = await self._remnawave_sdk.users.get_user_by_id(target.remnawave_user_id)
        if panel_user.expire_at < pinned:
            return  # the extension never landed
        # the row never took it, so its expiry is the one before the renewal
        before = (
            target.expire_at
            if data.duration_days == 0
            else pinned - timedelta(days=data.duration_days)
        )
        await self._remnawave_sdk.users.update_user(
            UpdateUserRequestDto(id=target.remnawave_user_id, expire_at=before)
        )
        logger.info(
            f"Reverted the panel extension of subscription '{target.id}' "
            "left by an unfinished renewal after a refund"
        )

    async def _shorten(
        self, actor: Actor, data: PurchaseRollbackDto, renewed: SubscriptionDto
    ) -> None:
        now = datetime_now()
        if data.duration_days == 0:
            before = refunded_unlimited_expiry(renewed.plan_snapshot, now)
        elif renewed.is_unlimited:
            # a later unlimited renewal replaced the refunded term: 2099 stays
            before = renewed.expire_at
        else:
            before = renewed.expire_at - timedelta(days=data.duration_days)
        if before != renewed.expire_at:
            await self._remnawave_sdk.users.update_user(
                UpdateUserRequestDto(id=renewed.remnawave_user_id, expire_at=before)
            )
        current = renewed
        try:
            async with self._uow:
                current = await self._subscription_repository.get_by_id_for_update(renewed.id)
                _assert_unchanged(current, renewed)
                paid = await self._paid_in_snapshot_currency(data, current)
                await self._lifecycle_service.shorten_after_refund(
                    current.id, days=data.duration_days, paid=paid, now=now
                )
                await self._publish(actor, current)
        except Exception:
            await self._revert_panel(current)
            raise

    async def _restore_replaced(
        self, actor: Actor, old: SubscriptionDto, new: SubscriptionDto
    ) -> None:
        now = datetime_now()
        # the plan change kept old's panel user, so putting its config back is enough
        await self._remnawave_sdk.users.update_user(restore(old))
        current = new
        try:
            async with self._uow:
                current = await self._subscription_repository.get_by_id_for_update(new.id)
                _assert_unchanged(current, new)
                # first: both rows share one panel user, live at most one at a time
                await self._subscription_repository.mark_deleted(new.id)
                await self._lifecycle_service.restore_after_refund(old.id, now)
                await self._publish(actor, current)
        except Exception:
            await self._revert_panel(current)
            raise

    async def _revert_panel(self, current: SubscriptionDto) -> None:
        await revert_panel_to_owner(
            self._remnawave_sdk, self._subscription_repository, self._uow, current
        )

    async def _paid_in_snapshot_currency(
        self, data: PurchaseRollbackDto, target: SubscriptionDto
    ) -> Decimal:
        currency = target.plan_snapshot.currency
        if data.price_paid <= 0 or data.currency is currency:
            return data.price_paid
        rates = await self._pricing_repository.get_rate_table()
        return rates.convert(data.price_paid, data.currency, currency)

    async def _publish(self, actor: Actor, subscription: SubscriptionDto) -> None:
        subscriber = await subscription_owner(self._user_repository, subscription)
        await self._event_publisher.publish(
            SubscriptionEditedEvent(
                actor=actor,
                target=subscriber,
                action="refund_rollback",
                subscription_id=subscription.id,
            )
        )
