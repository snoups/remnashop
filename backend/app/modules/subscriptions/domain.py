from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Final, Optional
from uuid import UUID

from remnapy.enums import TrafficLimitStrategy

from app.core.enums import SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.subscriptions.dto import PlanSnapshot

# Every status maps to the set of statuses it may transition into,
# including itself (a same-status write, e.g. a redelivered sync webhook,
# is always legal and a no-op). DELETED is terminal: once set, no further
# transition is legal from it, matching the existing DELETE semantics
# every usecase already assumes.
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
            SubscriptionStatus.ACTIVE,  # renew reactivates -- see reactivate_on_renew()
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
    """Behavioural counterpart to SubscriptionDto -- the repository maps
    an ORM row to this before calling a method, and the (possibly changed)
    result back to a row afterwards. Immutable: every method returns a new
    instance rather than mutating self, matching this codebase's existing
    frozen-dataclass DTO style (dto.py's Create/Update DTOs)."""

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
        stale panel event). The panel is authoritative — any other target
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
        again" case). LIMITED/DISABLED are left untouched -- those reflect
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

    def mark_deleted(self) -> SubscriptionState:
        assert_transition(self.status, SubscriptionStatus.DELETED)
        return replace(self, status=SubscriptionStatus.DELETED)


def calculate_proration_credit(
    *,
    price_paid: Decimal,
    duration_days: int,
    expire_at: datetime,
    is_trial: bool,
    now: datetime,
) -> Decimal:
    """Pure proration math -- a function of the OLD subscription's own
    fields only, with no dependency on what it's being changed to. Public
    (not `_`-prefixed) so a caller can preview the credit BEFORE committing
    a change_plan() transition -- e.g. to compute the new subscription's
    final expire_at (base days + credit days) before minting its panel
    identity, so the panel is minted with the correct value up front
    instead of a provisional one reconciled after the fact."""
    if is_trial or price_paid <= 0 or duration_days <= 0:
        return Decimal("0")
    remaining_days = max(0, (expire_at - now).days)
    daily_rate = price_paid / Decimal(duration_days)
    return daily_rate * Decimal(remaining_days)
