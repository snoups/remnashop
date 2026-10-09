from contextlib import suppress
from datetime import timedelta

from loguru import logger
from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import PurchaseSubscriptionDto, SubscriptionDto
from app.modules.subscriptions.eligibility import PurchaseEligibility
from app.modules.subscriptions.events import SubscriptionPurchasedEvent
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases.purchase_subscription.panel import (
    SupersededError,
    configure_for_plan,
    new_panel_user,
    reset_traffic_if_paid,
    restore,
    subscription_row,
)


class _AlreadyProvisionedError(Exception):
    def __init__(self, subscription_id: int) -> None:
        super().__init__(subscription_id)
        self.subscription_id = subscription_id


class NewPurchase:
    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        idempotency_repository: PurchaseIdempotencyRepository,
        eligibility: PurchaseEligibility,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._idempotency = idempotency_repository
        self._eligibility = eligibility
        self._remnawave_sdk = remnawave_sdk
        self._uow = uow
        self._event_publisher = event_publisher

    async def run(self, actor: Actor, data: PurchaseSubscriptionDto) -> SubscriptionDto:
        async with self._uow:
            if data.target_subscription_id is not None:
                raise ValidationError(
                    "target_subscription_id is forbidden for a NEW purchase",
                    code=ErrorCode.TARGET_SUBSCRIPTION_FORBIDDEN,
                )

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
            await self._eligibility.assert_below_cap(
                data.user_id, pending=await self._open_orders(data)
            )

        plan = data.plan_snapshot
        expire_at = datetime_now() + timedelta(days=data.duration_days)
        panel_user = await self._remnawave_sdk.users.create_user(
            new_panel_user(data.user_id, plan, expire_at)
        )

        try:
            async with self._uow:
                await self._assert_not_provisioned(data)
                if data.enforce_subscription_cap:
                    # Must come before the count-check below: FOR UPDATE on
                    # get_active_by_user_for_update only locks rows that already
                    # exist, so without this advisory lock two concurrent calls
                    # here could both observe the same under-cap count and both
                    # insert, silently exceeding the cap.
                    await self._subscription_repository.acquire_purchase_cap_lock(data.user_id)
                    await self._eligibility.assert_below_cap(
                        data.user_id, lock=True, pending=await self._open_orders(data)
                    )
                subscription = await self._subscription_repository.create(
                    subscription_row(data, panel_user)
                )
                await self._finish(actor, data, subscription)
        except _AlreadyProvisionedError as done:
            with suppress(Exception):
                await self._remnawave_sdk.users.disable_user(panel_user.id)
            async with self._uow:
                return await self._subscription_repository.get_by_id(done.subscription_id)
        except Exception:
            # disable, not delete: the DB write failed, not the panel user, and
            # a disabled user can still be inspected and restored
            with suppress(Exception):
                await self._remnawave_sdk.users.disable_user(panel_user.id)
            raise

        logger.info(
            f"{actor.log} Purchased subscription '{subscription.id}' (plan '{plan.plan_id}', NEW)"
        )
        return subscription

    async def _assert_not_provisioned(self, data: PurchaseSubscriptionDto) -> None:
        # a stale claim can be reclaimed; the attempt that reclaimed it may already have finished
        if data.idempotency_key is None:
            return
        finished_id = await self._idempotency.lock(data.idempotency_key)
        if finished_id is not None:
            raise _AlreadyProvisionedError(finished_id)

    async def _open_orders(self, data: PurchaseSubscriptionDto) -> int:
        # a trial is upgraded in place by a later paid order, so open orders don't crowd
        # it out; the order being fulfilled must not count against itself
        if data.plan_snapshot.is_trial:
            return 0
        return await self._eligibility.open_new_orders(
            data.user_id, exclude_key=data.idempotency_key
        )

    async def _upgrade_trial_in_place(
        self, actor: Actor, data: PurchaseSubscriptionDto, trial: SubscriptionDto
    ) -> SubscriptionDto:
        # the trial's panel user, reconfigured for the purchased plan; no
        # create_user/delete_user here
        plan = data.plan_snapshot
        expire_at = datetime_now() + timedelta(days=data.duration_days)
        panel_user = await self._remnawave_sdk.users.update_user(
            configure_for_plan(trial.remnawave_user_id, plan, expire_at)
        )

        try:
            async with self._uow:
                await self._assert_not_provisioned(data)
                locked_trial = await self._subscription_repository.get_by_id_for_update(trial.id)
                if locked_trial.status is SubscriptionStatus.DELETED:
                    raise SupersededError(
                        "Trial subscription was already converted or deleted while this "
                        "purchase was in flight",
                        code=ErrorCode.PURCHASE_SUPERSEDED,
                    )
                await self._subscription_repository.mark_deleted(trial.id)
                subscription = await self._subscription_repository.create(
                    # a disabled trial stays disabled: configure_for_plan
                    # leaves the panel status as it is
                    subscription_row(data, panel_user, status=SubscriptionStatus(panel_user.status))
                )
                await self._finish(actor, data, subscription)
        except _AlreadyProvisionedError as done:
            # no revert: the panel user now belongs to the finished subscription
            async with self._uow:
                return await self._subscription_repository.get_by_id(done.subscription_id)
        except SupersededError:
            raise
        except Exception:
            # best-effort revert, never disable: the panel user still belongs to
            # the reverted trial row
            with suppress(Exception):
                await self._remnawave_sdk.users.update_user(restore(trial))
            raise

        await reset_traffic_if_paid(self._remnawave_sdk, data, subscription)

        logger.info(
            f"{actor.log} Purchased subscription '{subscription.id}' "
            f"(plan '{plan.plan_id}', upgraded from trial '{trial.id}')"
        )
        return subscription

    async def _finish(
        self, actor: Actor, data: PurchaseSubscriptionDto, subscription: SubscriptionDto
    ) -> None:
        if data.idempotency_key is not None:
            await self._idempotency.link(data.idempotency_key, subscription.id)
        if not data.publish_event:
            return
        await self._event_publisher.publish(
            SubscriptionPurchasedEvent(
                user=actor,
                subscription_id=subscription.id,
                plan_id=data.plan_snapshot.plan_id,
                purchase_type=data.purchase_type.value,
                payment_key=data.idempotency_key,
            )
        )
