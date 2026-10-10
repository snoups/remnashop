from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Final, Optional
from uuid import UUID

from remnapy.enums import TrafficLimitStrategy

from app.core.constants import GB_TO_BYTES
from app.core.enums import SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.subscriptions.dto import PlanSnapshot


class SupersededError(ValidationError):
    """A concurrent purchase committed first and now owns the panel identity
    this one reconfigured; reverting it would overwrite the winner's config."""


# a subscription that still holds a panel identity and counts as owned
OWNED_STATUSES: Final[tuple[SubscriptionStatus, ...]] = (
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.DISABLED,
    SubscriptionStatus.LIMITED,
)

# Every status maps to the set of statuses it may transition into,
# including itself (a same-status write, e.g. a redelivered sync webhook,
# is always legal and a no-op). DELETED is terminal: once set, no further
# transition is legal from it.
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
    """Behavioural counterpart to SubscriptionDto: the repository maps
    an ORM row to this before calling a method, and the (possibly changed)
    result back to a row afterwards. Immutable: every method returns a new
    instance rather than mutating self."""

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
        """Applies a panel-driven status sync. A no-op if target == current
        (redelivered webhook / overlapping reconcile pass) or if already
        DELETED (a locally-deleted subscription is never resurrected by a
        stale panel event). The panel is authoritative: any other target
        status is accepted unconditionally."""
        if self.status is SubscriptionStatus.DELETED or target is self.status:
            return self
        return replace(self, status=target)

    def sync_expire_at(self, new_expire_at: datetime) -> SubscriptionState:
        """Applies a panel-driven expire_at. Status is never inferred from it --
        the panel reports its own status alongside (see sync_status)."""
        if self.status is SubscriptionStatus.DELETED:
            return self
        return replace(self, expire_at=new_expire_at)

    def reactivate_on_renew(self, new_expire_at: datetime) -> SubscriptionState:
        """A successful renewal always extends expire_at, and reactivates
        an EXPIRED subscription back to ACTIVE (the natural "lapsed, paid
        again" case). LIMITED/DISABLED are left untouched: those reflect
        panel-side state (traffic exhaustion, admin action) that a renewal
        payment doesn't by itself resolve; the next sync/reconcile pass
        corrects them once the panel agrees."""
        if self.status is SubscriptionStatus.DELETED:
            raise ValidationError(
                "Cannot renew a deleted subscription", code=ErrorCode.SUBSCRIPTION_DELETED
            )
        is_expired = self.status is SubscriptionStatus.EXPIRED
        target = SubscriptionStatus.ACTIVE if is_expired else self.status
        assert_transition(self.status, target)
        return replace(self, status=target, expire_at=new_expire_at)

    def add_renewal_credit(
        self, paid: Decimal, days: int, *, restart: bool = False
    ) -> SubscriptionState:
        snap = self.plan_snapshot
        # a lapsed term's money was used up; the new term starts its own credit
        base_paid = Decimal(0) if restart else snap.effective_credit_paid
        base_days = 0 if restart else snap.effective_credit_days
        return replace(
            self,
            plan_snapshot=replace(snap, credit_paid=base_paid + paid, credit_days=base_days + days),
        )

    def mark_deleted(self) -> SubscriptionState:
        assert_transition(self.status, SubscriptionStatus.DELETED)
        return replace(self, status=SubscriptionStatus.DELETED)


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
    """Proration credit from the OLD subscription's fields alone. Public so
    ChangePurchase can compute the new expire_at (base days + credit days)
    before touching the panel."""
    if is_trial or credit_paid <= 0 or credit_days <= 0:
        return Decimal("0")
    remaining_days = max(0, (expire_at - now).days)
    credit = min(credit_paid / Decimal(credit_days) * Decimal(remaining_days), credit_paid)
    # a resetting counter covers the current period, not the whole term
    if traffic_limit > 0 and traffic_limit_strategy is TrafficLimitStrategy.NO_RESET:
        limit_bytes = traffic_limit * GB_TO_BYTES
        remaining_bytes = max(0, limit_bytes - used_traffic_bytes)
        credit = min(credit, credit_paid * Decimal(remaining_bytes) / Decimal(limit_bytes))
    return credit
