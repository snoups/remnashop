from datetime import datetime, timedelta
from typing import Callable

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import ExtendUserRequestDto, UpdateUserRequestDto

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now, truncate_to_ms
from app.modules.subscriptions.dto import PurchaseSubscriptionDto, SubscriptionDto
from app.modules.subscriptions.events import SubscriptionRenewedEvent
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository


class RenewPurchase:
    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        idempotency_repository: PurchaseIdempotencyRepository,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        lifecycle_service: SubscriptionLifecycleService,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._idempotency = idempotency_repository
        self._remnawave_sdk = remnawave_sdk
        self._uow = uow
        self._event_publisher = event_publisher
        self._lifecycle_service = lifecycle_service

    async def run(
        self, actor: Actor, data: PurchaseSubscriptionDto, keep_key: Callable[[], None]
    ) -> SubscriptionDto:
        async with self._uow:
            if data.target_subscription_id is None:
                raise ValidationError(
                    "target_subscription_id is required for a RENEW",
                    code=ErrorCode.TARGET_SUBSCRIPTION_REQUIRED,
                )

            # Validate unlocked, call the panel, THEN lock+re-validate+apply --
            # never hold a row lock across the SDK round-trip: a remote call
            # inside `async with self._uow:` risks holding a Postgres lock for
            # the panel's full timeout.
            target = await self._subscription_repository.get_by_id(data.target_subscription_id)
            if target.status is SubscriptionStatus.DELETED:
                raise ValidationError(
                    "Cannot renew a deleted subscription", code=ErrorCode.SUBSCRIPTION_DELETED
                )
            if target.user_id != data.user_id:
                raise ValidationError(
                    "target_subscription_id does not belong to this user",
                    code=ErrorCode.TARGET_SUBSCRIPTION_NOT_OWNED,
                )
            if target.plan_snapshot.plan_id != data.plan_snapshot.plan_id:
                raise ValidationError(
                    "Renewing a different plan is a CHANGE, not a RENEW",
                    code=ErrorCode.RENEW_PLAN_MISMATCH,
                )

        if data.idempotency_key is None:
            # No retry path re-runs a keyless grant, so the panel's own atomic
            # relative extend is safe here.
            panel_user = await self._remnawave_sdk.users.extend_user(
                target.remnawave_user_id, ExtendUserRequestDto(days=data.duration_days)
            )
            expire_at = panel_user.expire_at
        else:
            expire_at = await self._apply_pinned_renewal(
                target, data.idempotency_key, data.duration_days, keep_key
            )

        async with self._uow:
            if data.idempotency_key is not None:
                finished_id = await self._idempotency.lock(data.idempotency_key)
                if finished_id is not None:
                    return await self._subscription_repository.get_by_id(finished_id)
            locked = await self._subscription_repository.get_by_id_for_update(target.id)
            if locked.status is SubscriptionStatus.DELETED:
                # Deleted (e.g. by a concurrent CHANGE or admin delete) while
                # the panel call was in flight. The panel's extend_user call
                # already landed against a real, still-existing panel user --
                # harmless (no orphan to compensate; the next sync/reconcile
                # pass corrects the panel-vs-local mismatch), so no cleanup
                # here, just refuse to reactivate.
                raise ValidationError(
                    "Subscription was deleted while this renewal was in flight",
                    code=ErrorCode.SUBSCRIPTION_DELETED,
                )
            subscription = await self._lifecycle_service.renew(locked.id, expire_at)
            if data.idempotency_key is not None:
                await self._idempotency.link(data.idempotency_key, subscription.id)
            await self._event_publisher.publish(
                SubscriptionRenewedEvent(
                    user=actor,
                    subscription_id=subscription.id,
                    duration_days=data.duration_days,
                    payment_key=data.idempotency_key,
                )
            )

        logger.info(
            f"{actor.log} Renewed subscription '{subscription.id}' by {data.duration_days}d"
        )
        return subscription

    async def _apply_pinned_renewal(
        self,
        target: SubscriptionDto,
        key: str,
        duration_days: int,
        keep_key: Callable[[], None],
    ) -> datetime:
        # Same result as the panel's extend (max(expire_at, now) + days, and an
        # EXPIRED user flips to ACTIVE on a future expireAt), but written as an
        # absolute value pinned before the call -- a lost response or a failed
        # commit is retried with that value instead of extending again.
        # a keyless extend landing between the read and the write
        # below is overwritten, and on resume an extension that pushed the
        # panel past the pinned value masks an unlanded write. A panel-side
        # idempotency token would close both.
        async with self._uow:
            pinned = await self._idempotency.get_pending_renew_expire_at(key)
        if pinned is None:
            panel_user = await self._remnawave_sdk.users.get_user_by_id(target.remnawave_user_id)
            base = max(panel_user.expire_at, datetime_now())
            # ms-truncated so the pinned value compares equal to the panel's
            pinned = truncate_to_ms(base + timedelta(days=duration_days))
            async with self._uow:
                await self._idempotency.pin_renew_expire_at(key, pinned)
            keep_key()
        else:
            keep_key()
            panel_user = await self._remnawave_sdk.users.get_user_by_id(target.remnawave_user_id)
            if panel_user.expire_at >= pinned:
                return pinned

        await self._remnawave_sdk.users.update_user(
            UpdateUserRequestDto(id=target.remnawave_user_id, expire_at=pinned)
        )
        return pinned
