from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Final, Optional
from uuid import UUID

from remnapy.enums import TrafficLimitStrategy

from app.core.enums import SubscriptionStatus
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
        raise ValidationError(f"Subscription status '{current}' -> '{target}' is not allowed")


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

    def reactivate_on_renew(self, new_expire_at: datetime) -> SubscriptionState:
        """A successful renewal always extends expire_at, and reactivates
        an EXPIRED subscription back to ACTIVE (the natural "lapsed, paid
        again" case). LIMITED/DISABLED are left untouched -- those reflect
        panel-side state (traffic exhaustion, admin action) that a renewal
        payment doesn't by itself resolve; the next sync/reconcile pass
        corrects them once the panel agrees."""
        if self.status is SubscriptionStatus.DELETED:
            raise ValidationError("Cannot renew a deleted subscription")
        is_expired = self.status is SubscriptionStatus.EXPIRED
        target = SubscriptionStatus.ACTIVE if is_expired else self.status
        assert_transition(self.status, target)
        return replace(self, status=target, expire_at=new_expire_at)

    def change_plan_in_place(
        self, *, new_plan_snapshot: PlanSnapshot, new_expire_at: datetime
    ) -> SubscriptionState:
        """Applies a CHANGE onto this same row and the same panel identity --
        id and (at the repository/panel level) remnawave_user_id never
        change, only the plan-driven fields do. Always lands ACTIVE,
        matching the "you just paid, you get access" semantics a CHANGE has
        always had, regardless of the pre-change status (LIMITED/DISABLED/
        EXPIRED all resolve to ACTIVE here, same as a fresh purchase would).
        new_expire_at is supplied, not computed here, because the caller
        needs the identical value before this runs -- to mint/update the
        panel identity with the correct final expire_at up front (see
        calculate_proration_credit's docstring)."""
        assert_transition(self.status, SubscriptionStatus.ACTIVE)
        return replace(
            self,
            status=SubscriptionStatus.ACTIVE,
            plan_snapshot=new_plan_snapshot,
            traffic_limit=new_plan_snapshot.traffic_limit,
            device_limit=new_plan_snapshot.device_limit,
            traffic_limit_strategy=new_plan_snapshot.traffic_limit_strategy,
            internal_squads=new_plan_snapshot.internal_squads,
            external_squad=new_plan_snapshot.external_squad,
            is_trial=new_plan_snapshot.is_trial,
            expire_at=new_expire_at,
        )

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
