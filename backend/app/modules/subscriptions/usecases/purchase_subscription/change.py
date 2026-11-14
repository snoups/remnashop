from contextlib import suppress
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

from loguru import logger
from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.pricing import PricingRepository
from app.modules.subscriptions.domain import SupersededError, calculate_proration_credit
from app.modules.subscriptions.dto import PlanSnapshot, PurchaseSubscriptionDto, SubscriptionDto
from app.modules.subscriptions.eligibility import get_owned_target
from app.modules.subscriptions.events import SubscriptionChangedEvent
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.panel import (
    configure_for_plan,
    reset_traffic_if_paid,
    restore,
    revert_panel_to_owner,
    subscription_row,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.unlimited import expiry_after


class _TargetMovedError(Exception):
    """The target moved after its panel user was configured from it: a renewal
    shifted expire_at (the credit is stale), or an addon grant pushed its own
    limits over this change's."""

    def __init__(self, current: SubscriptionDto) -> None:
        self.current = current


class ChangePurchase:
    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        idempotency_repository: PurchaseIdempotencyRepository,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        pricing_repository: PricingRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._idempotency = idempotency_repository
        self._remnawave_sdk = remnawave_sdk
        self._uow = uow
        self._event_publisher = event_publisher
        self._pricing_repository = pricing_repository

    async def run(self, actor: Actor, data: PurchaseSubscriptionDto) -> SubscriptionDto:
        if data.target_subscription_id is None:
            raise ValidationError(
                "target_subscription_id is required for a CHANGE",
                code=ErrorCode.TARGET_SUBSCRIPTION_REQUIRED,
            )
        if data.duration_days < 0:
            raise ValidationError(
                "duration_days can't be negative", code=ErrorCode.DURATION_NOT_POSITIVE
            )
        # the retry's update_user overwrites the stale expire_at the first one set
        with suppress(_TargetMovedError):
            return await self._attempt(actor, data, data.target_subscription_id)
        try:
            return await self._attempt(actor, data, data.target_subscription_id)
        except _TargetMovedError as moved:
            with suppress(Exception):
                await self._remnawave_sdk.users.update_user(restore(moved.current))
            raise SupersededError(
                "Subscription kept changing while this request was in flight",
                code=ErrorCode.PURCHASE_SUPERSEDED,
            ) from None

    async def _attempt(
        self, actor: Actor, data: PurchaseSubscriptionDto, target_id: int
    ) -> SubscriptionDto:
        async with self._uow:
            old = await get_owned_target(self._subscription_repository, target_id, data.user_id)
            if old.status is SubscriptionStatus.DELETED:
                raise ValidationError(
                    "Cannot change a deleted subscription", code=ErrorCode.SUBSCRIPTION_DELETED
                )

        plan, final_expire_at, credit_days = await self._new_term(old, data)

        # keeps old's panel user (same id, same subscription_url the client
        # already has) and changes only the plan config (limits, squads,
        # expiry); the local row is replaced below
        panel_user = await self._remnawave_sdk.users.update_user(
            configure_for_plan(old.remnawave_user_id, plan, final_expire_at)
        )

        try:
            async with self._uow:
                # a second plan change or a delete may have raced this one

                locked_old = await self._subscription_repository.get_by_id_for_update(old.id)
                if locked_old.status is SubscriptionStatus.DELETED:
                    raise SupersededError(
                        "Subscription was already changed or deleted while this request "
                        "was in flight",
                        code=ErrorCode.PURCHASE_SUPERSEDED,
                    )
                if (
                    locked_old.expire_at != old.expire_at
                    or locked_old.addon_entitlements != old.addon_entitlements
                ):
                    raise _TargetMovedError(locked_old)
                await self._subscription_repository.mark_deleted(old.id)
                updated = await self._subscription_repository.create(
                    subscription_row(
                        replace(data, plan_snapshot=plan),
                        panel_user,
                        expire_at=final_expire_at,
                        # an admin change can reach a disabled or expired panel user,
                        # which configure_for_plan leaves as it is
                        status=SubscriptionStatus(panel_user.status),
                    )
                )
                if data.idempotency_key is not None:
                    await self._idempotency.link(data.idempotency_key, updated.id, data.claim_token)
                if data.publish_event:
                    await self._event_publisher.publish(
                        SubscriptionChangedEvent(
                            user=actor,
                            subscription_id=updated.id,
                            previous_subscription_id=old.id,
                            previous_plan_snapshot=old.plan_snapshot.to_json(),
                            payment_key=data.idempotency_key,
                        )
                    )
        except SupersededError:
            # the row that replaced old owns the panel user now; give it its config back
            await revert_panel_to_owner(
                self._remnawave_sdk, self._subscription_repository, self._uow, old
            )
            raise
        except _TargetMovedError:
            raise
        except Exception:
            # no orphan: update_user changed old's own panel user. Best-effort
            # revert, so a DB failure doesn't leave the still-ACTIVE `old` on a
            # plan config nobody paid for
            with suppress(Exception):
                await self._remnawave_sdk.users.update_user(restore(old))
            raise

        if data.duration_days == 0 and old.is_unlimited and data.price_paid == ZERO_AMOUNT:
            # the credit paid for it all: switching back and forth mustn't buy a reset
            data = replace(data, reset_traffic=False)
        updated = await reset_traffic_if_paid(
            self._remnawave_sdk, self._subscription_repository, self._uow, data, updated
        )

        logger.info(
            f"{actor.log} Changed subscription '{old.id}' to plan '{plan.plan_id}' "
            f"({credit_days}d credit applied)"
        )
        return updated

    async def _new_term(
        self, old: SubscriptionDto, data: PurchaseSubscriptionDto
    ) -> tuple[PlanSnapshot, datetime, int]:
        """The new row's plan with its credit, its expiry and the days credited."""
        plan = data.plan_snapshot
        if data.keep_expire_at:
            credit_days = 0
            final_expire_at = old.expire_at
            # the term didn't change, so neither did the money paid for it
            plan = replace(
                plan,
                credit_paid=await self._convert(
                    old.plan_snapshot.effective_credit_paid,
                    old.plan_snapshot.currency,
                    plan.currency,
                ),
                credit_days=old.plan_snapshot.effective_credit_days,
            )
        elif data.duration_days == 0:
            credit_days = 0
            final_expire_at = expiry_after(datetime_now(), 0)
            # checkout took what an unlimited one was paid off the price; carried
            # on, so the next change to unlimited credits all of it again
            carried = (
                await self._convert(
                    old.plan_snapshot.effective_credit_paid,
                    old.plan_snapshot.currency,
                    plan.currency,
                )
                if old.is_unlimited and not old.is_trial
                else ZERO_AMOUNT
            )
            plan = replace(plan, credit_paid=plan.price_paid + carried, credit_days=0)
        else:
            now = datetime_now()
            credit, credit_days = await self._credit(old, data, now)
            final_expire_at = now + timedelta(days=data.duration_days + credit_days)
            # the new term carries the credit, so a later CHANGE may credit it back
            plan = replace(
                plan,
                credit_paid=plan.price_paid + credit,
                credit_days=plan.duration_days + credit_days,
            )
        return plan, final_expire_at, credit_days

    async def _credit(
        self, old: SubscriptionDto, data: PurchaseSubscriptionDto, now: datetime
    ) -> tuple[Decimal, int]:
        # depends on `old` alone, so the panel gets the final expire_at on the
        # first call
        panel_user = await self._remnawave_sdk.users.get_user_by_id(old.remnawave_user_id)
        credit = calculate_proration_credit(
            credit_paid=old.plan_snapshot.effective_credit_paid,
            credit_days=old.plan_snapshot.effective_credit_days,
            expire_at=old.expire_at,
            is_trial=old.is_trial,
            now=now,
            traffic_limit=old.effective_traffic_limit,
            traffic_limit_strategy=old.traffic_limit_strategy,
            used_traffic_bytes=int(panel_user.used_traffic_bytes),
        )
        credit = await self._convert(credit, old.plan_snapshot.currency, data.currency)
        # divided by the list price (data.base_price): at the discounted rate a
        # 90%-off checkout would buy 10x the credit days
        proration_denominator = data.base_price if data.base_price is not None else data.price_paid
        daily_rate_new = proration_denominator / Decimal(data.duration_days)
        if daily_rate_new <= 0:
            return ZERO_AMOUNT, 0
        return credit, int(credit / daily_rate_new)

    async def _convert(self, amount: Decimal, source: Currency, target: Currency) -> Decimal:
        if source is target:
            return amount
        async with self._uow:
            rates = await self._pricing_repository.get_rate_table()
        return rates.convert(amount, source, target)
