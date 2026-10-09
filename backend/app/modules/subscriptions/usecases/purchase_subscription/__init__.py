from contextlib import suppress
from datetime import timedelta
from typing import Final, Optional

from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PurchaseType
from app.core.error_codes import ErrorCode
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.pricing import PricingRepository
from app.modules.subscriptions.dto import PurchaseSubscriptionDto, SubscriptionDto
from app.modules.subscriptions.eligibility import PurchaseEligibility
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases.purchase_subscription.change import ChangePurchase
from app.modules.subscriptions.usecases.purchase_subscription.new import NewPurchase
from app.modules.subscriptions.usecases.purchase_subscription.renew import RenewPurchase

STALE_CLAIM_AFTER: Final[timedelta] = timedelta(minutes=15)


class PurchaseSubscriptionUseCase(UseCase[PurchaseSubscriptionDto, SubscriptionDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        eligibility: PurchaseEligibility,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        lifecycle_service: SubscriptionLifecycleService,
        pricing_repository: PricingRepository,
        idempotency_repository: PurchaseIdempotencyRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._idempotency = idempotency_repository
        self._uow = uow
        # one step per purchase type, sharing this usecase's dependencies
        self._new = NewPurchase(
            subscription_repository,
            idempotency_repository,
            eligibility,
            remnawave_sdk,
            uow,
            event_publisher,
        )
        self._renew = RenewPurchase(
            subscription_repository,
            idempotency_repository,
            remnawave_sdk,
            uow,
            event_publisher,
            lifecycle_service,
            pricing_repository,
        )
        self._change = ChangePurchase(
            subscription_repository,
            idempotency_repository,
            remnawave_sdk,
            uow,
            event_publisher,
            pricing_repository,
        )

    async def _execute(self, actor: Actor, data: PurchaseSubscriptionDto) -> SubscriptionDto:
        if data.user_id != actor.id and not actor.is_privileged:
            raise PermissionDeniedError

        if data.idempotency_key is not None:
            existing = await self._claim_or_return_existing(
                data.idempotency_key, data.purchase_type
            )
            if existing is not None:
                return existing

        # Releasing the key lets a retry (taskiq's own, or the reconcile sweep)
        # start over from scratch. A RENEW keeps its key once its target
        # expire_at is pinned: the retry then resumes with that same absolute
        # value instead of computing a new one. A NEW mints a fresh panel user
        # per attempt (and disables the failed one) and a CHANGE writes an
        # absolute expire_at, so both stay safe to start over.
        keep_key = False

        def mark_key_kept() -> None:
            nonlocal keep_key
            keep_key = True

        try:
            if data.purchase_type is PurchaseType.NEW:
                return await self._new.run(actor, data)
            if data.purchase_type is PurchaseType.RENEW:
                return await self._renew.run(actor, data, mark_key_kept)
            if data.purchase_type is PurchaseType.CHANGE:
                return await self._change.run(actor, data)
            raise NotImplementedError(f"purchase_type '{data.purchase_type}' not yet implemented")
        except BaseException:
            if not keep_key:
                await self._release_idempotency_key_best_effort(data.idempotency_key)
            raise

    async def _claim_or_return_existing(
        self, key: str, purchase_type: PurchaseType
    ) -> Optional[SubscriptionDto]:
        async with self._uow:
            claimed = await self._idempotency.claim(
                key, stale_before=datetime_now() - STALE_CLAIM_AFTER
            )
        async with self._uow:
            if claimed:
                return None
            existing_id = await self._idempotency.get_subscription_id(key)
            if existing_id is not None:
                return await self._subscription_repository.get_by_id(existing_id)
            if (
                purchase_type is PurchaseType.RENEW
                and await self._idempotency.get_pending_renew_expire_at(key) is not None
            ):
                return None  # resume: the renewal re-applies the pinned expire_at
            raise ValidationError(
                f"Purchase with idempotency_key '{key}' is already in progress",
                code=ErrorCode.PURCHASE_IN_PROGRESS,
            )

    async def _release_idempotency_key_best_effort(self, key: Optional[str]) -> None:
        if key is None:
            return
        with suppress(Exception):
            async with self._uow:
                await self._idempotency.release(key)
