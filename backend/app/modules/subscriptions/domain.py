from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final, Optional
from uuid import UUID

from remnapy.enums import TrafficLimitStrategy

from app.core.constants import GB_TO_BYTES, ZERO_AMOUNT
from app.core.enums import SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.subscriptions.dto import PlanSnapshot
from app.modules.subscriptions.unlimited import is_unlimited_expiry


class SupersededError(ValidationError):
    """A concurrent purchase committed first and now owns the panel identity
    this one reconfigured; reverting it would overwrite the winner's config."""


class OrderNotPaidError(SupersededError):
    """The order behind this purchase was refunded or failed while it was in flight."""


# a subscription that still holds a panel identity and counts as owned
OWNED_STATUSES: Final[tuple[SubscriptionStatus, ...]] = (
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.DISABLED,
    SubscriptionStatus.LIMITED,
)

# a status may always go to itself (a redelivered webhook); DELETED is terminal
VALID_TRANSITIONS: Final[dict[SubscriptionStatus, frozenset[SubscriptionStatus]]] = {
    SubscriptionStatus.ACTIVE: frozenset(
        {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.LIMITED,
            SubscriptionStatus.DISABLED,
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.DELETED,
        }
    ),
    SubscriptionStatus.LIMITED: frozenset(
        {
            SubscriptionStatus.LIMITED,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.DISABLED,
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.DELETED,
        }
    ),
    SubscriptionStatus.DISABLED: frozenset(
        {
            SubscriptionStatus.DISABLED,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.LIMITED,
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.DELETED,
        }
    ),
    SubscriptionStatus.EXPIRED: frozenset(
        {
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.ACTIVE,  # renew reactivates, see reactivate_on_renew()
            SubscriptionStatus.DELETED,
        }
    ),
    SubscriptionStatus.DELETED: frozenset({SubscriptionStatus.DELETED}),
}


def assert_transition(current: SubscriptionStatus, target: SubscriptionStatus) -> None:
    if target not in VALID_TRANSITIONS[current]:
        raise ValidationError(
            f"Subscription status '{current}' -> '{target}' is not allowed",
            code=ErrorCode.SUBSCRIPTION_STATUS_TRANSITION_INVALID,
        )


@dataclass(frozen=True, kw_only=True)
class SubscriptionState:
    """Behavioural counterpart to SubscriptionDto: the repository maps a row to
    it and the returned state back. Every method returns a new instance."""

    id: int
    status: SubscriptionStatus
    expire_at: datetime
    plan_snapshot: PlanSnapshot
    traffic_limit: int
    device_limit: int
    traffic_limit_strategy: TrafficLimitStrategy
    internal_squads: list[UUID]
    external_squad: Optional[UUID]
    is_trial: bool

    def sync_status(self, target: SubscriptionStatus) -> SubscriptionState:
        """The panel is authoritative: any status it reports is taken, except
        that a DELETED row is never resurrected by a stale panel event."""
        if self.status is SubscriptionStatus.DELETED or target is self.status:
            return self
        return replace(self, status=target)

    def sync_expire_at(self, new_expire_at: datetime) -> SubscriptionState:
        """Status is never inferred from expire_at: the panel reports its own."""
        if self.status is SubscriptionStatus.DELETED:
            return self
        return replace(self, expire_at=new_expire_at)

    def reactivate_on_renew(self, new_expire_at: datetime) -> SubscriptionState:
        """Extends expire_at and brings an EXPIRED subscription back to ACTIVE.
        LIMITED/DISABLED stay: a payment doesn't resolve traffic exhaustion or an
        admin's action, and the next sync corrects them once the panel agrees."""
        if self.status is SubscriptionStatus.DELETED:
            raise ValidationError(
                "Cannot renew a deleted subscription", code=ErrorCode.SUBSCRIPTION_DELETED
            )
        is_expired = self.status is SubscriptionStatus.EXPIRED
        target = SubscriptionStatus.ACTIVE if is_expired else self.status
        assert_transition(self.status, target)
        return replace(self, status=target, expire_at=new_expire_at)

    def add_renewal_credit(
        self,
        paid: Decimal,
        days: int,
        *,
        restart: bool = False,
        previous_expire_at: Optional[datetime] = None,
    ) -> SubscriptionState:
        snap = self.plan_snapshot
        if days == 0:
            # an unlimited term isn't prorated by days; what it replaced is kept
            # for a refund to put back
            return replace(
                self,
                plan_snapshot=replace(
                    snap,
                    credit_paid=paid,
                    credit_days=0,
                    unlimited_from=previous_expire_at,
                    unlimited_from_credit_paid=snap.effective_credit_paid,
                    unlimited_from_credit_days=snap.effective_credit_days,
                ),
            )
        # a lapsed term's money was used up, and an unlimited one's isn't prorated
        # by days: the new term starts its own credit
        fresh = restart or snap.effective_credit_days == 0
        base_paid = ZERO_AMOUNT if fresh else snap.effective_credit_paid
        base_days = 0 if fresh else snap.effective_credit_days
        return replace(
            self,
            plan_snapshot=replace(snap, credit_paid=base_paid + paid, credit_days=base_days + days),
        )

    def shorten_after_refund(self, days: int, paid: Decimal, now: datetime) -> SubscriptionState:
        """Takes a refunded renewal's term back off, with the credit it added."""
        if self.status is SubscriptionStatus.DELETED:
            raise ValidationError(
                "Cannot shorten a deleted subscription", code=ErrorCode.SUBSCRIPTION_DELETED
            )
        snap = self.plan_snapshot
        if days == 0:
            return self._undo_unlimited_renewal(now)
        expire_at = self.expire_at - timedelta(days=days)
        status = SubscriptionStatus.EXPIRED if expire_at <= now else self.status
        assert_transition(self.status, status)
        return replace(
            self,
            status=status,
            expire_at=expire_at,
            plan_snapshot=replace(
                snap,
                credit_paid=max(snap.effective_credit_paid - paid, ZERO_AMOUNT),
                credit_days=max(snap.effective_credit_days - days, 0),
            ),
        )

    def _undo_unlimited_renewal(self, now: datetime) -> SubscriptionState:
        """Back to the term an unlimited renewal replaced; without a record of
        it the refunded access ends now."""
        snap = self.plan_snapshot
        expire_at = refunded_unlimited_expiry(snap, now)
        status = SubscriptionStatus.EXPIRED if expire_at <= now else self.status
        assert_transition(self.status, status)
        return replace(
            self,
            status=status,
            expire_at=expire_at,
            plan_snapshot=replace(
                snap,
                credit_paid=snap.unlimited_from_credit_paid,
                credit_days=snap.unlimited_from_credit_days,
                unlimited_from=None,
                unlimited_from_credit_paid=None,
                unlimited_from_credit_days=None,
            ),
        )

    def restore_after_refund(self, now: datetime) -> SubscriptionState:
        """The one way out of DELETED: a refunded plan change puts the replaced
        row back, so VALID_TRANSITIONS is bypassed on purpose."""
        if self.status is not SubscriptionStatus.DELETED:
            raise ValidationError(
                f"Only a deleted subscription can be restored, not '{self.status}'",
                code=ErrorCode.SUBSCRIPTION_STATUS_TRANSITION_INVALID,
            )
        expired = self.expire_at <= now
        status = SubscriptionStatus.EXPIRED if expired else SubscriptionStatus.ACTIVE
        return replace(self, status=status)

    def mark_deleted(self) -> SubscriptionState:
        assert_transition(self.status, SubscriptionStatus.DELETED)
        return replace(self, status=SubscriptionStatus.DELETED)


def refunded_unlimited_expiry(snapshot: PlanSnapshot, now: datetime) -> datetime:
    return snapshot.unlimited_from if snapshot.unlimited_from is not None else now


def calculate_proration_credit(
    *,
    credit_paid: Decimal,
    credit_days: int,
    expire_at: datetime,
    is_trial: bool,
    now: datetime,
    traffic_limit: int,
    traffic_limit_strategy: TrafficLimitStrategy,
    used_traffic_bytes: int,
) -> Decimal:
    """Proration credit from the old subscription's fields alone, so ChangePurchase
    knows the new expire_at before touching the panel."""
    # an unlimited term has no remaining days to credit, whatever credit it still carries
    if is_trial or credit_paid <= 0 or credit_days <= 0 or is_unlimited_expiry(expire_at):
        return Decimal("0")
    remaining_days = max(0, (expire_at - now).days)
    credit = min(credit_paid / Decimal(credit_days) * Decimal(remaining_days), credit_paid)
    # a resetting counter covers the current period, not the whole term
    if traffic_limit > 0 and traffic_limit_strategy is TrafficLimitStrategy.NO_RESET:
        limit_bytes = traffic_limit * GB_TO_BYTES
        remaining_bytes = max(0, limit_bytes - used_traffic_bytes)
        credit = min(credit, credit_paid * Decimal(remaining_bytes) / Decimal(limit_bytes))
    return credit
