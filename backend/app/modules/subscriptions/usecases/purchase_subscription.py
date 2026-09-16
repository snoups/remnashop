from contextlib import suppress
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Final, Optional
from uuid import uuid4

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import (
    CreateUserRequestDto,
    ExtendUserRequestDto,
    UpdateUserRequestDto,
    UserResponseDto,
)

from app.core.constants import GB_TO_BYTES
from app.core.db.uow import UnitOfWork
from app.core.enums import PurchaseType, SubscriptionStatus
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now, truncate_to_ms
from app.modules.pricing import PricingRepository
from app.modules.settings import SettingsRepository
from app.modules.subscriptions.domain import calculate_proration_credit
from app.modules.subscriptions.dto import (
    CreateSubscriptionDto,
    PurchaseSubscriptionDto,
    SubscriptionDto,
)
from app.modules.subscriptions.events import (
    SubscriptionChangedEvent,
    SubscriptionPurchasedEvent,
    SubscriptionRenewedEvent,
)
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UpdateUserDto, UserDto, UserRepository

_PANEL_USERNAME_PREFIX: Final[str] = "rs_"


def _build_panel_username(user_id: int) -> str:
    return f"{_PANEL_USERNAME_PREFIX}{user_id}_{uuid4().hex[:8]}"


class PurchaseSubscriptionUseCase(UseCase[PurchaseSubscriptionDto, SubscriptionDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        settings_repository: SettingsRepository,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        lifecycle_service: SubscriptionLifecycleService,
        pricing_repository: PricingRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._settings_repository = settings_repository
        self._remnawave_sdk = remnawave_sdk
        self._uow = uow
        self._event_publisher = event_publisher
        self._lifecycle_service = lifecycle_service
        self._pricing_repository = pricing_repository

    async def _execute(self, actor: UserDto, data: PurchaseSubscriptionDto) -> SubscriptionDto:
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
        # value instead of computing a new one. _purchase_new mints a fresh
        # panel user per attempt (and disables the failed one) and _change
        # writes an absolute expire_at, so both stay safe to start over.
        keep_key = False

        def mark_key_kept() -> None:
            nonlocal keep_key
            keep_key = True

        try:
            if data.purchase_type is PurchaseType.NEW:
                return await self._purchase_new(actor, data)
            if data.purchase_type is PurchaseType.RENEW:
                return await self._renew(actor, data, mark_key_kept)
            if data.purchase_type is PurchaseType.CHANGE:
                return await self._change(actor, data)
            raise NotImplementedError(f"purchase_type '{data.purchase_type}' not yet implemented")
        except Exception:
            if not keep_key:
                await self._release_idempotency_key_best_effort(data.idempotency_key)
            raise

    async def _claim_or_return_existing(
        self, key: str, purchase_type: PurchaseType
    ) -> Optional[SubscriptionDto]:
        async with self._uow:
            claimed = await self._subscription_repository.claim_idempotency_key(key)
        async with self._uow:
            if claimed:
                return None
            existing = await self._subscription_repository.get_subscription_by_idempotency_key(key)
            if existing is not None:
                return existing
            if (
                purchase_type is PurchaseType.RENEW
                and await self._subscription_repository.get_pending_renew_expire_at(key) is not None
            ):
                return None  # resume -- _renew re-applies the pinned expire_at
            raise ValidationError(f"Purchase with idempotency_key '{key}' is already in progress")

    async def _clear_purchase_discount(self, data: PurchaseSubscriptionDto) -> None:
        # A discount is spent by being quoted against a price, so only a real
        # checkout consumes it -- a trial, a promocode reward or a referral
        # EXTRA_DAYS renewal all reach here too and would otherwise burn a
        # discount the customer never got to use. Within a checkout it's
        # cleared unconditionally: one no-op UPDATE is cheaper than a SELECT
        # to check first, and it's always correct either way.
        if not data.consumes_purchase_discount:
            return
        await self._user_repository.update_fields(data.user_id, UpdateUserDto(purchase_discount=0))

    async def _release_idempotency_key_best_effort(self, key: Optional[str]) -> None:
        if key is None:
            return
        with suppress(Exception):
            async with self._uow:
                await self._subscription_repository.release_idempotency_key(key)

    async def _purchase_new(self, actor: UserDto, data: PurchaseSubscriptionDto) -> SubscriptionDto:
        async with self._uow:
            if data.target_subscription_id is not None:
                raise ValidationError("target_subscription_id is forbidden for a NEW purchase")

            active_trial = next(
                (
                    sub
                    for sub in await self._subscription_repository.get_active_by_user(data.user_id)
                    if sub.is_trial
                ),
                None,
            )
        if active_trial is not None:
            return await self._upgrade_trial_in_place(actor, data, active_trial)

        # Unlocked pre-check so a purchase that's deterministically over the cap
        # never mints a panel user; the locked re-check below closes the race.
        if data.enforce_subscription_cap:
            await self._assert_under_subscription_cap(data.user_id, lock=False)

        plan = data.plan_snapshot
        username = _build_panel_username(data.user_id)
        expire_at = datetime_now() + timedelta(days=data.duration_days)

        panel_user = await self._remnawave_sdk.users.create_user(
            CreateUserRequestDto(
                username=username,
                expire_at=expire_at,
                traffic_limit_bytes=plan.traffic_limit * GB_TO_BYTES,
                traffic_limit_strategy=plan.traffic_limit_strategy,
                hwid_device_limit=plan.device_limit,
                active_internal_squads=plan.internal_squads or None,
                external_squad_uuid=plan.external_squad,
            )
        )

        try:
            async with self._uow:
                if data.enforce_subscription_cap:
                    # Must come before the count-check below: FOR UPDATE on
                    # get_active_by_user_for_update only locks rows that already
                    # exist, so without this advisory lock two concurrent calls
                    # here could both observe the same under-cap count and both
                    # insert, silently exceeding the cap.
                    await self._subscription_repository.acquire_purchase_cap_lock(data.user_id)
                    await self._assert_under_subscription_cap(data.user_id, lock=True)
                subscription = await self._subscription_repository.create(
                    self._to_create_dto(data, panel_user)
                )
                if data.idempotency_key is not None:
                    await self._subscription_repository.link_idempotency_key(
                        data.idempotency_key, subscription.id
                    )
                await self._event_publisher.publish(
                    SubscriptionPurchasedEvent(
                        user=actor,
                        subscription_id=subscription.id,
                        plan_id=plan.plan_id,
                        purchase_type=data.purchase_type.value,
                        payment_key=data.idempotency_key,
                    )
                )
                await self._clear_purchase_discount(data)
        except Exception:
            # disable, not delete: the DB write failed, not the panel user
            # itself -- disabling keeps a reversible, inspectable record on
            # the panel side instead of erasing it outright. Unlike
            # DeleteSubscriptionUseCase (a real, user-requested deletion),
            # this is purely compensating for our own failure.
            with suppress(Exception):
                await self._remnawave_sdk.users.disable_user(panel_user.id)
            raise

        logger.info(
            f"{actor.log} Purchased subscription '{subscription.id}' (plan '{plan.plan_id}', NEW)"
        )
        return subscription

    async def _assert_under_subscription_cap(self, user_id: int, *, lock: bool) -> None:
        shop_settings = await self._settings_repository.get_shop_settings()
        max_active = shop_settings.max_active_subscriptions
        if max_active is None:
            return
        if lock:
            active = await self._subscription_repository.get_active_by_user_for_update(user_id)
        else:
            active = await self._subscription_repository.get_active_by_user(user_id)
        if len(active) >= max_active:
            raise ValidationError(f"User '{user_id}' is already at the concurrent-subscription cap")

    async def _upgrade_trial_in_place(
        self, actor: UserDto, data: PurchaseSubscriptionDto, trial: SubscriptionDto
    ) -> SubscriptionDto:
        # Same panel identity, reconfigured for the purchased plan -- never
        # create_user/delete_user here, the trial's own identity is reused.
        plan = data.plan_snapshot
        expire_at = datetime_now() + timedelta(days=data.duration_days)

        panel_user = await self._remnawave_sdk.users.update_user(
            UpdateUserRequestDto(
                id=trial.remnawave_user_id,
                expire_at=expire_at,
                traffic_limit_bytes=plan.traffic_limit * GB_TO_BYTES,
                hwid_device_limit=plan.device_limit,
                traffic_limit_strategy=plan.traffic_limit_strategy,
                active_internal_squads=plan.internal_squads or None,
                external_squad_uuid=plan.external_squad,
            )
        )

        try:
            async with self._uow:
                locked_trial = await self._subscription_repository.get_by_id_for_update(trial.id)
                if locked_trial.status is SubscriptionStatus.DELETED:
                    raise ValidationError(
                        "Trial subscription was already converted or deleted while this "
                        "purchase was in flight"
                    )
                await self._subscription_repository.mark_deleted(trial.id)
                subscription = await self._subscription_repository.create(
                    self._to_create_dto(data, panel_user)
                )
                if data.idempotency_key is not None:
                    await self._subscription_repository.link_idempotency_key(
                        data.idempotency_key, subscription.id
                    )
                await self._event_publisher.publish(
                    SubscriptionPurchasedEvent(
                        user=actor,
                        subscription_id=subscription.id,
                        plan_id=plan.plan_id,
                        purchase_type=data.purchase_type.value,
                        payment_key=data.idempotency_key,
                    )
                )
                await self._clear_purchase_discount(data)
        except Exception:
            # Best-effort revert, never disable -- this panel identity still
            # belongs to the (reverted) trial row, not an orphan.
            with suppress(Exception):
                await self._remnawave_sdk.users.update_user(
                    UpdateUserRequestDto(
                        id=trial.remnawave_user_id,
                        expire_at=trial.expire_at,
                        traffic_limit_bytes=trial.traffic_limit * GB_TO_BYTES,
                        hwid_device_limit=trial.device_limit,
                        traffic_limit_strategy=trial.traffic_limit_strategy,
                        active_internal_squads=trial.internal_squads or None,
                        external_squad_uuid=trial.external_squad,
                    )
                )
            raise

        logger.info(
            f"{actor.log} Purchased subscription '{subscription.id}' "
            f"(plan '{plan.plan_id}', upgraded from trial '{trial.id}')"
        )
        return subscription

    async def _renew(
        self,
        actor: UserDto,
        data: PurchaseSubscriptionDto,
        keep_key: Callable[[], None],
    ) -> SubscriptionDto:
        async with self._uow:
            if data.target_subscription_id is None:
                raise ValidationError("target_subscription_id is required for a RENEW")

            # Validate unlocked, call the panel, THEN lock+re-validate+apply --
            # never hold a row lock across the SDK round-trip (core/db/uow.py's
            # own convention: a remote call inside `async with self._uow:` risks
            # holding a Postgres lock for the panel's full timeout). Matches
            # _purchase_new/_change's shape below, not the one this replaces.
            target = await self._subscription_repository.get_by_id(data.target_subscription_id)
            if target.status is SubscriptionStatus.DELETED:
                raise ValidationError("Cannot renew a deleted subscription")
            if target.user_id != data.user_id:
                raise ValidationError("target_subscription_id does not belong to this user")
            if target.plan_snapshot.plan_id != data.plan_snapshot.plan_id:
                raise ValidationError("Renewing a different plan is a CHANGE, not a RENEW")

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
                finished = await self._subscription_repository.lock_idempotency_key(
                    data.idempotency_key
                )
                if finished is not None:
                    return finished
            locked = await self._subscription_repository.get_by_id_for_update(target.id)
            if locked.status is SubscriptionStatus.DELETED:
                # Deleted (e.g. by a concurrent CHANGE or admin delete) while
                # the panel call was in flight. The panel's extend_user call
                # already landed against a real, still-existing panel user --
                # harmless (no orphan to compensate; the next sync/reconcile
                # pass corrects the panel-vs-local mismatch), so no cleanup
                # here, just refuse to reactivate.
                raise ValidationError("Subscription was deleted while this renewal was in flight")
            subscription = await self._lifecycle_service.renew(locked.id, expire_at)
            if data.idempotency_key is not None:
                await self._subscription_repository.link_idempotency_key(
                    data.idempotency_key, subscription.id
                )
            await self._event_publisher.publish(
                SubscriptionRenewedEvent(
                    user=actor,
                    subscription_id=subscription.id,
                    duration_days=data.duration_days,
                    payment_key=data.idempotency_key,
                )
            )
            await self._clear_purchase_discount(data)

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
            pinned = await self._subscription_repository.get_pending_renew_expire_at(key)
        if pinned is None:
            panel_user = await self._remnawave_sdk.users.get_user_by_id(target.remnawave_user_id)
            base = max(panel_user.expire_at, datetime_now())
            # ms-truncated so the pinned value compares equal to the panel's
            pinned = truncate_to_ms(base + timedelta(days=duration_days))
            async with self._uow:
                await self._subscription_repository.pin_renew_expire_at(key, pinned)
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

    async def _change(self, actor: UserDto, data: PurchaseSubscriptionDto) -> SubscriptionDto:
        async with self._uow:
            if data.target_subscription_id is None:
                raise ValidationError("target_subscription_id is required for a CHANGE")
            if data.duration_days <= 0:
                raise ValidationError("duration_days must be positive")

            old = await self._subscription_repository.get_by_id(data.target_subscription_id)
            if old.user_id != data.user_id:
                raise ValidationError("target_subscription_id does not belong to this user")
            if old.status is SubscriptionStatus.DELETED:
                raise ValidationError("Cannot change a deleted subscription")

            plan = data.plan_snapshot

            now = datetime_now()
            # Pure function of `old`'s own fields -- computable up front, before
            # the panel is ever touched, so it gets the CORRECT final expire_at
            # the first time. No provisional value, no post-hoc reconciliation,
            # no panel/DB mismatch.
            credit = calculate_proration_credit(
                price_paid=old.plan_snapshot.price_paid,
                duration_days=old.plan_snapshot.duration_days,
                expire_at=old.expire_at,
                is_trial=old.is_trial,
                now=now,
            )
            if old.plan_snapshot.currency is not data.currency:
                rates = await self._pricing_repository.get_rate_table()
                credit = (
                    credit
                    / rates.for_currency(old.plan_snapshot.currency).rate
                    * rates.for_currency(data.currency).rate
                )
            # Denominator is the list price (data.base_price), so the credit
            # converts at list rate -- at the promo-discounted rate a 90%-off
            # checkout would buy 10x the credit days it's worth.
            proration_denominator = (
                data.base_price if data.base_price is not None else data.price_paid
            )
            daily_rate_new = proration_denominator / Decimal(data.duration_days)
            credit_days = int(credit / daily_rate_new) if daily_rate_new > 0 else 0
            final_expire_at = now + timedelta(days=data.duration_days + credit_days)

        # Reuses old's own panel identity (same UUID, same subscription_url
        # the client may already have) instead of minting a new one -- only
        # the plan-driven config (limits/squads/expiry) changes on the panel
        # side. The local row itself is replaced below, not mutated.
        panel_user = await self._remnawave_sdk.users.update_user(
            UpdateUserRequestDto(
                id=old.remnawave_user_id,
                expire_at=final_expire_at,
                traffic_limit_bytes=plan.traffic_limit * GB_TO_BYTES,
                hwid_device_limit=plan.device_limit,
                traffic_limit_strategy=plan.traffic_limit_strategy,
                active_internal_squads=plan.internal_squads or None,
                external_squad_uuid=plan.external_squad,
            )
        )

        try:
            async with self._uow:
                # Re-fetch under lock and re-validate nothing changed
                # concurrently (e.g. a second CHANGE/DELETE racing this one)
                # before committing.
                locked_old = await self._subscription_repository.get_by_id_for_update(old.id)
                if locked_old.status is SubscriptionStatus.DELETED:
                    raise ValidationError(
                        "Subscription was already changed or deleted while this request "
                        "was in flight"
                    )
                await self._subscription_repository.mark_deleted(old.id)
                updated = await self._subscription_repository.create(
                    self._to_create_dto(data, panel_user, expire_at_override=final_expire_at)
                )
                if data.idempotency_key is not None:
                    await self._subscription_repository.link_idempotency_key(
                        data.idempotency_key, updated.id
                    )
                await self._event_publisher.publish(
                    SubscriptionChangedEvent(
                        user=actor,
                        subscription_id=updated.id,
                        previous_subscription_id=old.id,
                        previous_plan_snapshot=old.plan_snapshot.to_json(),
                        payment_key=data.idempotency_key,
                    )
                )
                await self._clear_purchase_discount(data)
        except Exception:
            # There's no orphan to clean up -- update_user mutated old's own
            # panel identity in place, no new one was minted. Best-effort
            # revert it to what it had before this CHANGE, so a DB failure
            # doesn't leave the still-ACTIVE `old` subscription pointing at
            # a panel user configured for a plan it was never billed for.
            with suppress(Exception):
                await self._remnawave_sdk.users.update_user(
                    UpdateUserRequestDto(
                        id=old.remnawave_user_id,
                        expire_at=old.expire_at,
                        traffic_limit_bytes=old.traffic_limit * GB_TO_BYTES,
                        hwid_device_limit=old.device_limit,
                        traffic_limit_strategy=old.traffic_limit_strategy,
                        active_internal_squads=old.internal_squads or None,
                        external_squad_uuid=old.external_squad,
                    )
                )
            raise

        logger.info(
            f"{actor.log} Changed subscription '{old.id}' to plan '{plan.plan_id}' "
            f"({credit_days}d credit applied)"
        )
        return updated

    def _to_create_dto(
        self,
        data: PurchaseSubscriptionDto,
        panel_user: UserResponseDto,
        expire_at_override: Optional[datetime] = None,
    ) -> CreateSubscriptionDto:
        plan = data.plan_snapshot
        return CreateSubscriptionDto(
            user_id=data.user_id,
            remnawave_user_id=panel_user.id,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=plan.traffic_limit,
            device_limit=plan.device_limit,
            traffic_limit_strategy=plan.traffic_limit_strategy,
            is_trial=plan.is_trial,
            internal_squads=plan.internal_squads,
            external_squad=plan.external_squad,
            expire_at=expire_at_override or panel_user.expire_at,
            url=panel_user.subscription_url,
            plan_snapshot=plan,
        )
