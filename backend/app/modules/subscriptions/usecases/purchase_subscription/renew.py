from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Optional

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
from app.modules.pricing import PricingRepository
from app.modules.subscriptions.domain import OrderNotPaidError
from app.modules.subscriptions.dto import PurchaseSubscriptionDto, SubscriptionDto
from app.modules.subscriptions.eligibility import get_owned_target
from app.modules.subscriptions.events import SubscriptionRenewedEvent
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.panel import revert_panel_to_owner
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
        pricing_repository: PricingRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._idempotency = idempotency_repository
        self._remnawave_sdk = remnawave_sdk
        self._uow = uow
        self._event_publisher = event_publisher
        self._lifecycle_service = lifecycle_service
        self._pricing_repository = pricing_repository

    async def run(
        self, actor: Actor, data: PurchaseSubscriptionDto, keep_key: Callable[[], None]
    ) -> SubscriptionDto:
        async with self._uow:
            if data.target_subscription_id is None:
                raise ValidationError(
                    "target_subscription_id is required for a RENEW",
                    code=ErrorCode.TARGET_SUBSCRIPTION_REQUIRED,
                )

            # validated unlocked, then the panel call, then lock, re-check and
            # apply: a row lock held across the panel call lasts up to its timeout
            target = await get_owned_target(
                self._subscription_repository, data.target_subscription_id, data.user_id
            )
            if target.status is SubscriptionStatus.DELETED:
                raise ValidationError(
                    "Cannot renew a deleted subscription", code=ErrorCode.SUBSCRIPTION_DELETED
                )
            # before the panel call: refusing after it would leave the panel
            # extended and a pinned key a caller can only retry, never undo
            if data.refuse_disabled_target and target.status is SubscriptionStatus.DISABLED:
                raise ValidationError(
                    "Cannot renew a disabled subscription", code=ErrorCode.SUBSCRIPTION_DISABLED
                )
            if target.plan_snapshot.plan_id != data.plan_snapshot.plan_id:
                raise ValidationError(
                    "Renewing a different plan is a CHANGE, not a RENEW",
                    code=ErrorCode.RENEW_PLAN_MISMATCH,
                )

        if data.idempotency_key is None:
            # No retry path re-runs a keyless grant, so the panel's atomic
            # relative extend is safe here.
            panel_user = await self._remnawave_sdk.users.extend_user(
                target.remnawave_user_id, ExtendUserRequestDto(days=data.duration_days)
            )
            expire_at = panel_user.expire_at
        else:
            expire_at = await self._apply_pinned_renewal(
                target, data.idempotency_key, data.claim_token, data.duration_days, keep_key
            )

        try:
            return await self._finish(actor, data, target, expire_at)
        except OrderNotPaidError:
            # refunded while the panel was being extended: take the extension back
            await revert_panel_to_owner(
                self._remnawave_sdk, self._subscription_repository, self._uow, target
            )
            raise

    async def _finish(
        self,
        actor: Actor,
        data: PurchaseSubscriptionDto,
        target: SubscriptionDto,
        expire_at: datetime,
    ) -> SubscriptionDto:
        async with self._uow:
            if data.idempotency_key is not None:
                finished_id = await self._idempotency.lock(data.idempotency_key, data.claim_token)
                if finished_id is not None:
                    return await self._subscription_repository.get_by_id(finished_id)
            locked = await self._subscription_repository.get_by_id_for_update(target.id)
            if locked.status is SubscriptionStatus.DELETED:
                # deleted by a concurrent plan change or admin while the panel
                # call ran; the extend landed on a live panel user, so there's
                # nothing to undo and the next sync settles the difference
                raise ValidationError(
                    "Subscription was deleted while this renewal was in flight",
                    code=ErrorCode.SUBSCRIPTION_DELETED,
                )
            paid = await self._paid_in_snapshot_currency(data, locked)
            subscription = await self._lifecycle_service.renew(
                locked.id, expire_at, paid=paid, days=data.duration_days
            )
            if data.idempotency_key is not None:
                await self._idempotency.link(
                    data.idempotency_key, subscription.id, data.claim_token
                )
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

    async def _paid_in_snapshot_currency(
        self, data: PurchaseSubscriptionDto, target: SubscriptionDto
    ) -> Decimal:
        currency = target.plan_snapshot.currency
        if data.price_paid <= 0 or data.currency is currency:
            return data.price_paid
        rates = await self._pricing_repository.get_rate_table()
        return rates.convert(data.price_paid, data.currency, currency)

    async def _apply_pinned_renewal(
        self,
        target: SubscriptionDto,
        key: str,
        token: Optional[datetime],
        duration_days: int,
        keep_key: Callable[[], None],
    ) -> datetime:
        # Same result as the panel's extend (max(expire_at, now) + days, an
        # EXPIRED user flips to ACTIVE on a future expireAt), but as an absolute
        # value pinned before the call, so a lost response or failed commit is
        # retried with it instead of extending twice.
        # Known gap: an extend from elsewhere between the read and the write is
        # overwritten, and on resume an extension past the pinned value hides
        # an unlanded write. A panel-side idempotency token would close both.
        async with self._uow:
            pinned = await self._idempotency.find_pending_renew_expire_at(key)
        if pinned is None:
            panel_user = await self._remnawave_sdk.users.get_user_by_id(target.remnawave_user_id)
            base = max(panel_user.expire_at, datetime_now())
            # ms-truncated so the pinned value compares equal to the panel's
            pinned = truncate_to_ms(base + timedelta(days=duration_days))
            async with self._uow:
                await self._idempotency.pin_renew_expire_at(key, pinned, token)
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
