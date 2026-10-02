from contextlib import suppress
from datetime import datetime, timedelta
from decimal import Decimal

from loguru import logger
from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.pricing import PricingRepository
from app.modules.subscriptions.domain import calculate_proration_credit
from app.modules.subscriptions.dto import PurchaseSubscriptionDto, SubscriptionDto
from app.modules.subscriptions.eligibility import get_owned_target
from app.modules.subscriptions.events import SubscriptionChangedEvent
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases.purchase_subscription.panel import (
    SupersededError,
    configure_for_plan,
    restore,
    subscription_row,
)


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
        async with self._uow:
            if data.target_subscription_id is None:
                raise ValidationError(
                    "target_subscription_id is required for a CHANGE",
                    code=ErrorCode.TARGET_SUBSCRIPTION_REQUIRED,
                )
            if data.duration_days <= 0:
                raise ValidationError(
                    "duration_days must be positive", code=ErrorCode.DURATION_NOT_POSITIVE
                )

            old = await get_owned_target(
                self._subscription_repository, data.target_subscription_id, data.user_id
            )
            if old.status is SubscriptionStatus.DELETED:
                raise ValidationError(
                    "Cannot change a deleted subscription", code=ErrorCode.SUBSCRIPTION_DELETED
                )

            now = datetime_now()
            credit_days = await self._credit_days(old, data, now)
            final_expire_at = now + timedelta(days=data.duration_days + credit_days)

        # Reuses old's own panel identity (same UUID, same subscription_url
        # the client may already have) instead of minting a new one -- only
        # the plan-driven config (limits/squads/expiry) changes on the panel
        # side. The local row itself is replaced below, not mutated.
        plan = data.plan_snapshot
        panel_user = await self._remnawave_sdk.users.update_user(
            configure_for_plan(old.remnawave_user_id, plan, final_expire_at)
        )

        try:
            async with self._uow:
                # Re-fetch under lock and re-validate nothing changed
                # concurrently (e.g. a second CHANGE/DELETE racing this one)
                # before committing.
                locked_old = await self._subscription_repository.get_by_id_for_update(old.id)
                if locked_old.status is SubscriptionStatus.DELETED:
                    raise SupersededError(
                        "Subscription was already changed or deleted while this request "
                        "was in flight",
                        code=ErrorCode.PURCHASE_SUPERSEDED,
                    )
                await self._subscription_repository.mark_deleted(old.id)
                updated = await self._subscription_repository.create(
                    subscription_row(data, panel_user, expire_at=final_expire_at)
                )
                if data.idempotency_key is not None:
                    await self._idempotency.link(data.idempotency_key, updated.id)
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
            raise
        except Exception:
            # There's no orphan to clean up -- update_user mutated old's own
            # panel identity in place, no new one was minted. Best-effort
            # revert it to what it had before this CHANGE, so a DB failure
            # doesn't leave the still-ACTIVE `old` subscription pointing at
            # a panel user configured for a plan it was never billed for.
            with suppress(Exception):
                await self._remnawave_sdk.users.update_user(restore(old))
            raise

        logger.info(
            f"{actor.log} Changed subscription '{old.id}' to plan '{plan.plan_id}' "
            f"({credit_days}d credit applied)"
        )
        return updated

    async def _credit_days(
        self, old: SubscriptionDto, data: PurchaseSubscriptionDto, now: datetime
    ) -> int:
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
        proration_denominator = data.base_price if data.base_price is not None else data.price_paid
        daily_rate_new = proration_denominator / Decimal(data.duration_days)
        return int(credit / daily_rate_new) if daily_rate_new > 0 else 0
